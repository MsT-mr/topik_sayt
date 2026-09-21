import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import Student, Vocabulary, Exam, ExamQuestion, ExamResult, StudentMessage


@ensure_csrf_cookie
@xframe_options_exempt
def index(request):
    """Asosiy HTML Mini App sahifasini yuklaydi"""
    return render(request, "index.html")


@require_POST
@csrf_exempt
def login_api(request):
    from .curriculum_views import student_data
    try:
        data = json.loads(request.body or b"{}")
        if not isinstance(data, dict) or not isinstance(data.get("student_id"), str):
            raise ValueError
        student_id = data["student_id"].strip().upper()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Ustoz bergan ID ni kiriting."}, status=400)
    student = Student.objects.select_related("group").filter(student_id=student_id, is_active=True).first()
    if not student:
        return JsonResponse({"detail": "ID topilmadi yoki hisob faol emas. Ustoz bergan ID ni tekshiring."}, status=403)
    request.session.cycle_key()
    request.session["student_pk"] = student.pk
    student.update_streak()
    return JsonResponse({"authenticated": True, "student": student_data(student)})


@require_GET
def get_vocabulary_api(request):
    from .curriculum_views import current_student
    student = current_student(request)
    if not student:
        return JsonResponse({"detail": "Avval ID bilan kiring."}, status=401)
    queryset = Vocabulary.objects.filter(lesson__book_level=student.book_level)
    lesson = request.GET.get("lesson")
    if lesson:
        if not lesson.isdigit():
            return JsonResponse({"detail": "Dars raqami noto‘g‘ri."}, status=400)
        queryset = queryset.filter(lesson_id=int(lesson))
    return JsonResponse(list(queryset.values("id", "korean", "translation", "level", "lesson_id")), safe=False)


def get_exams_api(request):
    """Mavjud faol TOPIK imtihonlari ro'yxati"""
    exams = Exam.objects.filter(is_active=True).order_by("level", "id")
    result = []
    for exam in exams:
        result.append({
            "id": exam.id,
            "title": exam.title,
            "description": exam.description,
            "level": exam.level,
            "duration_minutes": exam.duration_minutes,
            "pass_score": exam.pass_score,
            "questions_count": exam.questions.count(),
        })
    return JsonResponse(result, safe=False)


def get_exam_detail_api(request, exam_id):
    """Imtihon savollarini yuklaydi (javoblarsiz)"""
    exam = get_object_or_404(Exam, id=exam_id, is_active=True)
    questions = exam.questions.all().order_by("order", "id")

    q_list = []
    for q in questions:
        q_list.append({
            "id": q.id,
            "order": q.order,
            "question_type": q.question_type,
            "question_type_display": q.get_question_type_display(),
            "question_text": q.question_text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            }
        })

    return JsonResponse({
        "exam": {
            "id": exam.id,
            "title": exam.title,
            "description": exam.description,
            "level": exam.level,
            "duration_minutes": exam.duration_minutes,
            "pass_score": exam.pass_score,
            "total_questions": len(q_list),
        },
        "questions": q_list
    })


@csrf_exempt
def submit_exam_api(request, exam_id):
    """Talaba javoblarini qabul qilib tekshiradi va natijani bazaga yozadi"""
    if request.method != "POST":
        return JsonResponse({"detail": "Faqat POST so'rovi qabul qilinadi."}, status=405)

    try:
        exam = get_object_or_404(Exam, id=exam_id)
        data = json.loads(request.body.decode("utf-8") or "{}")

        student_id = data.get("student_id", "").strip().upper()
        telegram_id = data.get("telegram_id")
        user_answers = data.get("answers", {})  # {"question_id": "A", ...}

        student = Student.objects.filter(pk=request.session.get("student_pk"), is_active=True).first()
        if not student:
            return JsonResponse({"detail": "Avval ID orqali kiring."}, status=401)

        questions = exam.questions.all().order_by("order", "id")
        total_questions = questions.count()

        if total_questions == 0:
            return JsonResponse({"detail": "Ushbu imtihonda savollar mavjud emas."}, status=400)

        correct_count = 0
        questions_review = []

        for q in questions:
            user_choice = str(user_answers.get(str(q.id), "")).strip().upper()
            is_correct = (user_choice == q.correct_option)
            if is_correct:
                correct_count += 1

            questions_review.append({
                "id": q.id,
                "order": q.order,
                "question_text": q.question_text,
                "user_answer": user_choice,
                "correct_answer": q.correct_option,
                "is_correct": is_correct,
                "explanation": q.explanation or "Tushuntirish mavjud emas."
            })

        score_percentage = round((correct_count / total_questions) * 100, 1)
        passed = score_percentage >= exam.pass_score

        # Natijani bazaga saqlash
        result = ExamResult.objects.create(
            student=student,
            exam=exam,
            total_questions=total_questions,
            correct_answers=correct_count,
            score_percentage=score_percentage,
            passed=passed,
            answers_data=user_answers
        )

        # Talabaning umumiy ko'rsatkichlarini yangilash
        student.tests_completed += 1
        student.update_streak()
        student.save(update_fields=["tests_completed"])

        return JsonResponse({
            "result_id": result.id,
            "exam_title": exam.title,
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "score_percentage": score_percentage,
            "passed": passed,
            "completed_at": result.completed_at.strftime("%Y-%m-%d %H:%M"),
            "student_stats": {
                "streak": student.streak,
                "tests_completed": student.tests_completed,
            },
            "review": questions_review
        })

    except Exception as e:
        return JsonResponse({"detail": f"Natijani tekshirishda xatolik: {str(e)}"}, status=500)


def get_student_results_api(request, student_id):
    """O'quvchining barcha topshirgan imtihonlari tarixi"""
    student = get_object_or_404(Student, pk=request.session.get("student_pk"), student_id=student_id.strip().upper(), is_active=True)
    results = student.exam_results.select_related("exam").all()[:20]

    items = []
    for r in results:
        items.append({
            "id": r.id,
            "exam_title": r.exam.title,
            "level": r.exam.level,
            "total_questions": r.total_questions,
            "correct_answers": r.correct_answers,
            "score_percentage": r.score_percentage,
            "passed": r.passed,
            "completed_at": r.completed_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({"student_id": student.student_id, "results": items})

@require_GET
def inbox_api(request):
    student = Student.objects.filter(pk=request.session.get("student_pk"), is_active=True).first()
    if not student:
        return JsonResponse({"detail": "Avval saytga kiring."}, status=401)
    inbox = student.messages.select_related("announcement").order_by("-announcement__created_at", "-pk")[:100]
    return JsonResponse({"messages": [{"id": message.pk, "text": message.announcement.text,
        "created_at": timezone.localtime(message.announcement.created_at).strftime("%d.%m.%Y %H:%M"),
        "read": message.read_at is not None} for message in inbox]})


@require_POST
def read_message_api(request, message_id):
    student = Student.objects.filter(pk=request.session.get("student_pk"), is_active=True).first()
    if not student:
        return JsonResponse({"detail": "Avval saytga kiring."}, status=401)
    message = get_object_or_404(StudentMessage, pk=message_id, student=student)
    if message.read_at is None:
        message.read_at = timezone.now()
        message.save(update_fields=["read_at"])
    return JsonResponse({"read": True})
