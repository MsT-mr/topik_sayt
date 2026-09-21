import json
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from .models import Student, Lesson, Vocabulary, Grammar, WordProgress, GrammarProgress


def current_student(request):
    return Student.objects.select_related('group').filter(pk=request.session.get('student_pk'), is_active=True).first()


def student_data(student):
    total = Vocabulary.objects.filter(lesson__book_level=student.book_level).count()
    learned = student.word_progress.filter(learned=True, word__lesson__book_level=student.book_level).count()
    return {'id': student.student_id, 'name': student.name, 'book_level': student.book_level,
            'group': student.group.name if student.group else '', 'streak': student.streak,
            'words': student.words_learned, 'tests': student.tests_completed,
            'level_words': learned, 'total_words': total, 'progress': round(learned / total * 100) if total else 0}


def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        student = current_student(request)
        if not student:
            return JsonResponse({'detail': 'Avval ustoz bergan ID bilan kiring.'}, status=401)
        return view(request, student, *args, **kwargs)
    return wrapped


@require_GET
@login_required
def me(request, student):
    return JsonResponse({'authenticated': True, 'student': student_data(student)})


@require_POST
def logout(request):
    request.session.pop('student_pk', None)
    return JsonResponse({'ok': True})


@require_GET
@login_required
def lessons(request, student):
    learned = dict(student.word_progress.filter(learned=True).values('word__lesson_id').annotate(total=Count('id')).values_list('word__lesson_id','total'))
    read = dict(student.grammar_progress.values('grammar__lesson_id').annotate(total=Count('id')).values_list('grammar__lesson_id','total'))
    qs = Lesson.objects.filter(book_level=student.book_level).annotate(word_count=Count('words', distinct=True), grammar_count=Count('grammar', distinct=True))
    return JsonResponse({'student': student_data(student), 'lessons': [
        {'id': lesson.pk, 'number': lesson.number, 'title': lesson.title, 'book_level': lesson.book_level,
         'word_count': lesson.word_count, 'grammar_count': lesson.grammar_count,
         'learned': learned.get(lesson.pk, 0), 'grammar_read': read.get(lesson.pk, 0)} for lesson in qs]})


@require_GET
@login_required
def lesson_detail(request, student, lesson_id):
    from .services.lesson_guides import load_guide
    lesson = get_object_or_404(Lesson, pk=lesson_id, book_level=student.book_level)
    learned = set(student.word_progress.filter(learned=True, word__lesson=lesson).values_list('word_id', flat=True))
    read = set(student.grammar_progress.filter(grammar__lesson=lesson).values_list('grammar_id', flat=True))
    return JsonResponse({'lesson': {'id':lesson.pk, 'title':lesson.title,'number':lesson.number,'book_level':lesson.book_level},
        'guide': load_guide(lesson),
        'words':[{'id':w.pk,'korean':w.korean,'translation':w.translation,'learned':w.pk in learned} for w in lesson.words.all()],
        'grammar':[{'id':g.pk,'source_key':g.source_key,'title':g.title,'explanation':g.explanation,'examples':g.examples,'read':g.pk in read} for g in lesson.grammar.all()]})


@require_POST
@login_required
def word_progress(request, student, word_id):
    word = get_object_or_404(Vocabulary, pk=word_id, lesson__book_level=student.book_level)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or type(data.get('learned')) is not bool:
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'So‘z holati noto‘g‘ri.'}, status=400)
    with transaction.atomic():
        WordProgress.objects.update_or_create(student=student, word=word, defaults={'learned':data['learned']})
        student.words_learned = student.word_progress.filter(learned=True).count()
        student.save(update_fields=['words_learned'])
        student.update_streak()
    return JsonResponse({'student':student_data(student)})


@require_POST
@login_required
def grammar_progress(request, student, grammar_id):
    grammar = get_object_or_404(Grammar, pk=grammar_id, lesson__book_level=student.book_level)
    GrammarProgress.objects.get_or_create(student=student, grammar=grammar)
    student.update_streak()
    return JsonResponse({'read':True})
