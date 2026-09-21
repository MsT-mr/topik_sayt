from django.urls import path
from . import views, curriculum_views as curriculum, practice_views as practice
from . import ai_views

urlpatterns = [
    path("api/ai/tutor/", ai_views.tutor),
    path("api/ai/test/", ai_views.create_test),
    path("api/practice/", practice.catalog),
    path("api/practice/start/", practice.start),
    path("api/practice/<uuid:attempt_id>/submit/", practice.submit),
    path("api/practice/<uuid:attempt_id>/ai/", practice.attempt_ai),
    path("api/ai/study/", practice.study_ai),
    path("auth/me/", curriculum.me),
    path("auth/logout/", curriculum.logout),
    path("api/lessons/", curriculum.lessons),
    path("api/lessons/<int:lesson_id>/", curriculum.lesson_detail),
    path("api/words/<int:word_id>/progress/", curriculum.word_progress),
    path("api/grammar/<int:grammar_id>/progress/", curriculum.grammar_progress),
    path("api/messages/", views.inbox_api, name="inbox_api"),
    path("api/messages/<int:message_id>/read/", views.read_message_api, name="read_message_api"),
    # Asosiy sahifa
    path("", views.index, name="index"),

    # Auth
    path("auth/login/", views.login_api, name="login_api"),
    path("auth/login", views.login_api),

    # Lug'at API
    path("api/vocabulary/", views.get_vocabulary_api, name="vocabulary_api"),
    path("api/vocabulary", views.get_vocabulary_api),

    # Imtihon API lari
    path("api/exams/", views.get_exams_api, name="exams_api"),
    path("api/exams", views.get_exams_api),
    path("api/exams/<int:exam_id>/", views.get_exam_detail_api, name="exam_detail_api"),
    path("api/exams/<int:exam_id>", views.get_exam_detail_api),
    path("api/exams/<int:exam_id>/submit/", views.submit_exam_api, name="submit_exam_api"),
    path("api/exams/<int:exam_id>/submit", views.submit_exam_api),
    path("api/student/<str:student_id>/results/", views.get_student_results_api, name="student_results_api"),
    path("api/student/<str:student_id>/results", views.get_student_results_api),
]
