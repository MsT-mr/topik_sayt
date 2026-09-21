import secrets
import uuid
from django.core.exceptions import ValidationError
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from django.db import models, transaction


BOOK_LEVELS = [(value, value) for value in ("1A", "1B", "2A", "2B")]


class StudyGroup(models.Model):
    name = models.CharField("Guruh nomi", max_length=100)
    book_level = models.CharField("Kitob bosqichi", max_length=2, choices=BOOK_LEVELS, unique=True)
    notes = models.TextField("Izoh", blank=True)

    def __str__(self):
        return f"{self.book_level} — {self.name}"

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ["book_level", "name"]


class Student(models.Model):
    book_level = models.CharField("Kitob bosqichi", max_length=2, choices=BOOK_LEVELS, default="1A")
    group = models.ForeignKey(StudyGroup, verbose_name="Guruh", null=True, blank=True, on_delete=models.SET_NULL, related_name="students")
    is_active = models.BooleanField("Faol", default=True)
    teacher_notes = models.TextField("Ustoz qaydlari", blank=True)

    student_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name="Student ID"
    )
    telegram_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="Telegram ID"
    )
    name = models.CharField(
        max_length=150,
        default="",
        verbose_name="F.I.SH"
    )
    streak = models.IntegerField(default=0, verbose_name="Ketma-ket kunlar")
    words_learned = models.IntegerField(default=0, verbose_name="Yodlangan so'zlar")
    tests_completed = models.IntegerField(default=0, verbose_name="Yechilgan testlar")
    last_active_date = models.DateField(null=True, blank=True, verbose_name="Oxirgi faollik kuni")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqti")

    @property
    def full_name(self):
        """Telegram bot va template larda ishlatilgan full_name bilan moslik uchun"""
        return self.name

    @full_name.setter
    def full_name(self, value):
        self.name = value

    def update_streak(self):
        """Kunlik streakni mantiqiy yangilash"""
        today = timezone.now().date()
        if not self.last_active_date:
            self.streak = 1
            self.last_active_date = today
            self.save(update_fields=["streak", "last_active_date"])
        elif self.last_active_date == today:
            pass
        elif self.last_active_date == today - timedelta(days=1):
            self.streak += 1
            self.last_active_date = today
            self.save(update_fields=["streak", "last_active_date"])
        else:
            self.streak = 1
            self.last_active_date = today
            self.save(update_fields=["streak", "last_active_date"])

    def save(self, *args, **kwargs):
        if not self.student_id:
            while True:
                generated_id = f"TOPIK-{secrets.randbelow(90000000) + 10000000}"
                if not Student.objects.filter(student_id=generated_id).exists():
                    self.student_id = generated_id
                    break
        update_fields = kwargs.get("update_fields")
        if not self.pk or update_fields is None or "book_level" in update_fields:
            with transaction.atomic():
                self.group, _ = StudyGroup.objects.get_or_create(book_level=self.book_level, defaults={"name": f"{self.book_level} guruhi"})
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"group"}
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.student_id})"

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"


class Vocabulary(models.Model):
    order = models.PositiveIntegerField("Darsdagi tartib", default=1)
    source_key = models.CharField("Manba kaliti", max_length=100, unique=True, null=True, blank=True, editable=False)
    source_page = models.PositiveIntegerField("PDF sahifasi", null=True, blank=True, editable=False)
    lesson = models.ForeignKey("Lesson", verbose_name="Dars", null=True, blank=True, on_delete=models.PROTECT, related_name="words")
    korean = models.CharField(max_length=100, verbose_name="Koreyscha so'z")
    translation = models.CharField(max_length=200, verbose_name="O'zbekcha tarjimasi")
    level = models.IntegerField(default=1, verbose_name="TOPIK Daraja (1-6)")

    def __str__(self):
        return f"{self.korean} - {self.translation}"

    class Meta:
        verbose_name = "Lug'at so'zi"
        verbose_name_plural = "Lug'at"
        ordering = ["lesson", "order", "id"]


class Exam(models.Model):
    lesson = models.ForeignKey("Lesson", verbose_name="Dars", null=True, blank=True, on_delete=models.PROTECT, related_name="exams")
    title = models.CharField(max_length=200, verbose_name="Imtihon nomi")
    description = models.TextField(blank=True, default="", verbose_name="Tavsif")
    level = models.IntegerField(default=1, verbose_name="TOPIK Daraja (1-6)")
    duration_minutes = models.IntegerField(default=20, verbose_name="Vaqt (daqiqa)")
    pass_score = models.IntegerField(default=60, verbose_name="O'tish bali (%)")
    is_active = models.BooleanField(default=True, verbose_name="Faolmi?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqti")

    def __str__(self):
        return f"{self.title} (TOPIK {self.level})"

    class Meta:
        verbose_name = "TOPIK Imtihon"
        verbose_name_plural = "TOPIK Imtihonlari"


class ExamQuestion(models.Model):
    QUESTION_TYPES = [
        ("reading", "O'qish (Reading)"),
        ("listening", "Eshitish (Listening)"),
        ("grammar", "Grammatika"),
        ("vocabulary", "Lug'at"),
    ]

    OPTION_CHOICES = [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
    ]

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Imtihon"
    )
    question_text = models.TextField(verbose_name="Savol matni / Matn")
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default="reading",
        verbose_name="Savol turi"
    )
    option_a = models.CharField(max_length=255, verbose_name="A variant")
    option_b = models.CharField(max_length=255, verbose_name="B variant")
    option_c = models.CharField(max_length=255, verbose_name="C variant")
    option_d = models.CharField(max_length=255, verbose_name="D variant")
    correct_option = models.CharField(
        max_length=1,
        choices=OPTION_CHOICES,
        verbose_name="To'g'ri javob"
    )
    explanation = models.TextField(
        blank=True,
        default="",
        verbose_name="Tushuntirish / Izoh (AI Tutor)"
    )
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib raqami")

    def __str__(self):
        return f"{self.exam.title} - Savol #{self.order}"

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Imtihon savoli"
        verbose_name_plural = "Imtihon savollari"


class ExamResult(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="exam_results",
        verbose_name="O'quvchi"
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="Imtihon"
    )
    total_questions = models.IntegerField(default=0, verbose_name="Jami savollar")
    correct_answers = models.IntegerField(default=0, verbose_name="To'g'ri javoblar")
    score_percentage = models.FloatField(default=0.0, verbose_name="Ball foizi (%)")
    passed = models.BooleanField(default=False, verbose_name="O'tdimi?")
    answers_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Berilgan javoblar"
    )
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name="Tugatilgan vaqti")

    def __str__(self):
        return f"{self.student.name} - {self.exam.title}: {self.score_percentage}%"

    class Meta:
        ordering = ["-completed_at"]
        verbose_name = "Imtihon natijasi"
        verbose_name_plural = "Imtihon natijalari"

class Lesson(models.Model):
    book_level = models.CharField("Kitob bosqichi", max_length=2, choices=BOOK_LEVELS)
    number = models.PositiveIntegerField("Dars raqami")
    title = models.CharField("Mavzu", max_length=200)

    def __str__(self):
        return f"{self.book_level} / {self.number}-dars: {self.title}"

    class Meta:
        ordering = ["book_level", "number"]
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        constraints = [models.UniqueConstraint(fields=["book_level", "number"], name="unique_book_lesson")]


class Grammar(models.Model):
    source_key = models.CharField("Manba kaliti", max_length=100, unique=True, null=True, blank=True, editable=False)
    source_page = models.PositiveIntegerField("PDF sahifasi", null=True, blank=True, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="grammar", verbose_name="Dars")
    title = models.CharField("Qoida", max_length=255)
    explanation = models.TextField("O‘zbekcha izoh")
    examples = models.TextField("Misollar", blank=True)
    order = models.PositiveIntegerField("Tartib", default=1)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["lesson", "order"]
        verbose_name = "Grammatika qoidasi"
        verbose_name_plural = "Grammatika"


class Announcement(models.Model):
    text = models.TextField("Xabar matni", max_length=4000)
    audience = models.CharField("Qabul qiluvchilar", max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, verbose_name="Yuborgan ustoz")
    created_at = models.DateTimeField("Yuborilgan vaqt", auto_now_add=True)

    def __str__(self):
        return self.text[:70]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar tarixi"


class StudentMessage(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="deliveries", verbose_name="Xabar")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="messages", verbose_name="O‘quvchi")
    read_at = models.DateTimeField("Saytda o‘qilgan vaqt", null=True, blank=True)

    class Meta:
        verbose_name = "Xabar oluvchi"
        verbose_name_plural = "Xabar oluvchilar"
        constraints = [models.UniqueConstraint(fields=["announcement", "student"], name="unique_message_student")]


class WordProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="word_progress", verbose_name="O‘quvchi")
    word = models.ForeignKey(Vocabulary, on_delete=models.CASCADE, related_name="progress", verbose_name="So‘z")
    learned = models.BooleanField("Yodlangan", default=False)
    updated_at = models.DateTimeField("Oxirgi mashq", auto_now=True)

    class Meta:
        verbose_name = "So‘z o‘rganish natijasi"
        verbose_name_plural = "So‘z o‘rganish natijalari"
        constraints = [models.UniqueConstraint(fields=["student", "word"], name="unique_student_word")]


class GrammarProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grammar_progress", verbose_name="O‘quvchi")
    grammar = models.ForeignKey(Grammar, on_delete=models.CASCADE, related_name="progress", verbose_name="Qoida")
    updated_at = models.DateTimeField("O‘qilgan vaqt", auto_now=True)

    class Meta:
        verbose_name = "O‘qilgan grammatika"
        verbose_name_plural = "O‘qilgan grammatika qoidalari"
        constraints = [models.UniqueConstraint(fields=["student", "grammar"], name="unique_student_grammar")]


class GrammarExercise(models.Model):
    grammar = models.ForeignKey(Grammar, on_delete=models.PROTECT, related_name='exercises', verbose_name='Qoida va dars')
    source_key = models.CharField(max_length=100, unique=True, null=True, blank=True, editable=False)
    sentence = models.CharField('Bo‘sh joyli gap (___)', max_length=500)
    translation = models.CharField('Gapning o‘zbekcha ma’nosi', max_length=500)
    options = models.JSONField('Javob variantlari (ro‘yxat)')
    correct_index = models.PositiveSmallIntegerField('To‘g‘ri variant indeksi (0 dan)')
    explanation = models.TextField('Javob izohi')
    is_active = models.BooleanField('Faol', default=True)

    def clean(self):
        super().clean()
        if self.sentence.count('___') != 1:
            raise ValidationError({'sentence': 'Gapda aynan bitta ___ bo‘sh joy bo‘lsin.'})
        if not isinstance(self.options, list) or not 2 <= len(self.options) <= 4 or any(not isinstance(v, str) or not v.strip() for v in self.options):
            raise ValidationError('2–4 ta bo‘sh bo‘lmagan matnli variant kiriting.')
        if len(set(self.options)) != len(self.options):
            raise ValidationError('Variantlar takrorlanmasin.')
        if self.correct_index is None or self.correct_index >= len(self.options):
            raise ValidationError('To‘g‘ri variant indeksini tekshiring.')

    def __str__(self):
        return f'{self.grammar.lesson.book_level} · {self.sentence}'

    class Meta:
        verbose_name = 'Grammatika mashqi'
        verbose_name_plural = 'Grammatika mashqlari'


class PracticeAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='practice_attempts', verbose_name='O‘quvchi')
    book_level = models.CharField('Kitob bosqichi', max_length=2, choices=BOOK_LEVELS)
    questions = models.JSONField('Savollar nusxasi', default=list)
    answers = models.JSONField('Javoblar', default=dict)
    score = models.PositiveSmallIntegerField('To‘g‘ri javoblar', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField('Tugatilgan vaqt', null=True, blank=True)
    ai_analysis = models.TextField('AI tavsiyasi', blank=True)
    ai_model = models.CharField('AI modeli', max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Grammatika mashqi natijasi'
        verbose_name_plural = 'Grammatika mashqi natijalari'
