import json
import random
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .curriculum_views import login_required, student_data, review_levels
from .models import GrammarExercise, PracticeAttempt, Student, Vocabulary
from .services.gemini import analyze, AIUnavailable


def read_body(request):
    data = json.loads(request.body or b'{}')
    if not isinstance(data, dict):
        raise ValueError
    return data


def review(attempt):
    return [dict(sentence=q['sentence'], translation=q['translation'], lesson=q['lesson'], rule=q['rule'],
                 correct=q['options'][q['correct_index']], chosen=q['options'][attempt.answers[str(i)]],
                 is_correct=attempt.answers[str(i)] == q['correct_index'], explanation=q['explanation'])
            for i, q in enumerate(attempt.questions)]


def result_data(attempt):
    total = len(attempt.questions)
    return {'id':str(attempt.pk),'book_level':attempt.book_level,'score':attempt.score,'total':total,
            'percentage':round(attempt.score/total*100) if total else 0, 'review':review(attempt),
            'ai_analysis':attempt.ai_analysis, 'ai_model':attempt.ai_model,
            'ai_available':bool(settings.GEMINI_API_KEY)}


@require_GET
@login_required
def catalog(request, student):
    qs = GrammarExercise.objects.filter(is_active=True, grammar__lesson__book_level__in=review_levels(student))
    return JsonResponse({'book_level':student.book_level, 'grammar_count':qs.count(),
                         'ai_available':bool(settings.GEMINI_API_KEY)})


@require_GET
@login_required
def vocabulary_review(request, student):
    levels = review_levels(student)
    previous_levels = tuple(level for level in levels if level != student.book_level)

    current = list(Vocabulary.objects.filter(
        lesson__book_level=student.book_level
    ).select_related("lesson"))
    previous = list(Vocabulary.objects.filter(
        lesson__book_level__in=previous_levels
    ).select_related("lesson")) if previous_levels else []

    rng = random.SystemRandom()
    rng.shuffle(current)
    rng.shuffle(previous)

    limit = 30
    if previous:
        previous_count = min(len(previous), limit // 2)
        current_count = min(len(current), limit - previous_count)
        chosen = previous[:previous_count] + current[:current_count]
        if len(chosen) < limit:
            leftovers = previous[previous_count:] + current[current_count:]
            rng.shuffle(leftovers)
            chosen += leftovers[:limit - len(chosen)]
    else:
        chosen = current[:limit]

    rng.shuffle(chosen)
    learned_ids = set(student.word_progress.filter(
        learned=True, word_id__in=[w.pk for w in chosen]
    ).values_list("word_id", flat=True))

    return JsonResponse({
        "book_level": student.book_level,
        "review_levels": list(levels),
        "words": [{
            "id": w.pk,
            "korean": w.korean,
            "translation": w.translation,
            "book_level": w.lesson.book_level if w.lesson else "",
            "lesson": w.lesson.number if w.lesson else None,
            "learned": w.pk in learned_ids,
        } for w in chosen],
    })


@require_POST
@login_required
def start(request, student):
    try:
        data = read_body(request)
        lesson = data.get('lesson_id')
        if lesson is not None and (type(lesson) is not int or lesson < 1):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail':'Dars tanlovini tekshiring.'}, status=400)
    qs = GrammarExercise.objects.filter(is_active=True, grammar__lesson__book_level__in=review_levels(student)).select_related('grammar__lesson')
    if lesson is not None:
        qs = qs.filter(grammar__lesson_id=lesson)
    exercises = list(qs)
    if not exercises:
        return JsonResponse({'detail':'Bu daraja yoki dars uchun grammatika mashqlari hali yo‘q.'}, status=404)
    random.SystemRandom().shuffle(exercises)
    questions = []
    for exercise in exercises[:10]:
        # Shuffle choices on each attempt, retaining the correct index only on the server.
        indexed = list(enumerate(exercise.options))
        random.SystemRandom().shuffle(indexed)
        questions.append({'exercise_id':exercise.pk, 'sentence':exercise.sentence,
                          'translation':exercise.translation, 'rule':exercise.grammar.title,
                          'lesson':exercise.grammar.lesson.number, 'options':[o for _,o in indexed],
                          'correct_index':next(i for i,(old,_) in enumerate(indexed) if old==exercise.correct_index),
                          'explanation':exercise.explanation})
    # A double click / network retry reuses the unfinished attempt for the same selection.
    existing = student.practice_attempts.filter(book_level=student.book_level, completed_at__isnull=True, created_at__gte=timezone.now()-timedelta(hours=2)).first()
    selected_ids = {q['exercise_id'] for q in questions}
    if existing and {q['exercise_id'] for q in existing.questions} == selected_ids:
        attempt = existing
    else:
        attempt = PracticeAttempt.objects.create(student=student, book_level=student.book_level, questions=questions)
    public = [{k:v for k,v in q.items() if k not in ('correct_index','explanation','rule','exercise_id')} for q in attempt.questions]
    return JsonResponse({'id':str(attempt.pk),'book_level':attempt.book_level,'questions':public})


@require_POST
@login_required
def submit(request, student, attempt_id):
    attempt = get_object_or_404(PracticeAttempt, pk=attempt_id, student=student)
    if attempt.completed_at:
        return JsonResponse(result_data(attempt))
    if attempt.book_level != student.book_level:
        return JsonResponse({'detail':'Ustoz darajangizni o‘zgartirdi. Mashqni yangidan boshlang.'}, status=409)
    try:
        answers = read_body(request).get('answers')
        if not isinstance(answers, dict) or set(answers) != {str(i) for i in range(len(attempt.questions))}:
            raise ValueError
        if any(type(answers[str(i)]) is not int or not 0 <= answers[str(i)] < len(q['options']) for i,q in enumerate(attempt.questions)):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail':'Har bir savolda bitta variantni tanlang.'}, status=400)
    score = sum(answers[str(i)] == q['correct_index'] for i,q in enumerate(attempt.questions))
    with transaction.atomic():
        updated = PracticeAttempt.objects.filter(pk=attempt.pk, completed_at__isnull=True).update(answers=answers, score=score, completed_at=timezone.now())
        if updated:
            Student.objects.filter(pk=student.pk).update(tests_completed=F('tests_completed')+1)
            student.update_streak()
    attempt.refresh_from_db()
    return JsonResponse(result_data(attempt))


@require_POST
@login_required
def attempt_ai(request, student, attempt_id):
    attempt = get_object_or_404(PracticeAttempt, pk=attempt_id, student=student, completed_at__isnull=False)
    if attempt.ai_analysis:
        return JsonResponse({'text':attempt.ai_analysis,'model':attempt.ai_model})
    key = f'practice-ai:{student.pk}'
    if not cache.add(key, True, timeout=45):
        return JsonResponse({'detail':'AI tahlili so‘ralgan. Birozdan keyin qayta urinib ko‘ring.'}, status=429)
    try:
        data = analyze({'book_level':attempt.book_level, 'correct':attempt.score, 'total':len(attempt.questions), 'review':review(attempt)})
        attempt.ai_analysis = data['text']
        attempt.ai_model = data['model']
        attempt.save(update_fields=['ai_analysis','ai_model'])
        return JsonResponse(data)
    except AIUnavailable as error:
        return JsonResponse({'detail':str(error)}, status=503)


@require_POST
@login_required
def study_ai(request, student):
    key = f'study-ai:{student.pk}:{student.book_level}'
    cached = cache.get(key)
    if cached:
        return JsonResponse(cached)
    if not cache.add(f'practice-ai:{student.pk}', True, timeout=45):
        return JsonResponse({'detail':'Birozdan keyin qayta urinib ko‘ring.'}, status=429)
    attempts = list(student.practice_attempts.filter(book_level=student.book_level, completed_at__isnull=False)[:3])
    info = student_data(student)
    evidence = {'book_level':student.book_level,'self_reported_words':info['level_words'],
                'total_words':info['total_words'], 'read_grammar':student.grammar_progress.filter(grammar__lesson__book_level=student.book_level).count(),
                'recent_practice':[{'score':a.score,'total':len(a.questions),'review':review(a)} for a in attempts]}
    if not attempts and not info['level_words']:
        cache.delete(f'practice-ai:{student.pk}')
        return JsonResponse({'detail':'Avval lug‘at yoki grammatika mashqini bajaring. Shundan so‘ng natijangiz asosida tavsiya beriladi.'}, status=400)
    try:
        data = analyze(evidence)
        cache.set(key, data, timeout=300)
        return JsonResponse(data)
    except AIUnavailable as error:
        return JsonResponse({'detail':str(error)}, status=503)
