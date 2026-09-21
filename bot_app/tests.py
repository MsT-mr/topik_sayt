import json
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import Student, StudyGroup, Announcement, StudentMessage


class TeacherPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = get_user_model().objects.create_superuser('teacher_test', password='test-password')
        cls.group = StudyGroup.objects.get_or_create(book_level='1A', defaults={'name':'Birinchi guruh'})[0]
        cls.other = StudyGroup.objects.get_or_create(book_level='2B', defaults={'name':'Ikkinchi guruh'})[0]
        cls.first = Student.objects.create(name='Birinchi', group=cls.group)
        cls.second = Student.objects.create(name='Ikkinchi', group=cls.group)
        cls.outside = Student.objects.create(name='Boshqa', book_level='2B', group=cls.other)
        cls.inactive = Student.objects.create(name='Nofaol', group=cls.group, is_active=False)

    def setUp(self):
        self.client.force_login(self.teacher)

    def payload(self, **kwargs):
        return {'level': '1A', 'group': self.group.pk, 'mode': 'all', 'text': 'Omad!', **kwargs}

    def test_group_all_excludes_other_and_inactive(self):
        response = self.client.post(reverse('admin:topik_compose'), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertSetEqual(set(StudentMessage.objects.values_list('student_id', flat=True)), {self.first.pk, self.second.pk})

    def test_individual_and_cross_group_validation(self):
        response = self.client.post(reverse('admin:topik_compose'), self.payload(mode='one', student=self.outside.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Announcement.objects.count(), 0)
        self.client.post(reverse('admin:topik_compose'), self.payload(mode='one', student=self.second.pk))
        self.assertEqual(StudentMessage.objects.get().student, self.second)

    def test_recipient_list_is_filtered_and_has_ids(self):
        data = self.client.get(reverse('admin:topik_recipients'), {'level': '1A', 'group': self.group.pk}).json()
        self.assertEqual(len(data['students']), 2)
        self.assertIn(self.first.student_id, data['students'][0]['label'])

    def test_admin_pages_render(self):
        urls = ['admin:index', 'admin:bot_app_student_changelist', 'admin:bot_app_studygroup_changelist', 'admin:bot_app_announcement_changelist', 'admin:topik_compose']
        for name in urls:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        for model, pk in [('student', self.first.pk), ('studygroup', self.group.pk)]:
            self.assertEqual(self.client.get(reverse(f'admin:bot_app_{model}_change', args=[pk])).status_code, 200)

    def test_nonstaff_cannot_send(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse('admin:topik_compose'), self.payload()).status_code, 302)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_only_teacher_issued_ids_work(self):
        self.client.logout()
        before = Student.objects.count()
        self.assertEqual(self.client.post('/auth/login/', json.dumps({'student_id': 'NO-SUCH-ID'}), content_type='application/json').status_code, 403)
        self.assertEqual(Student.objects.count(), before)
        self.assertEqual(self.client.post('/auth/login/', json.dumps({'student_id': self.inactive.student_id}), content_type='application/json').status_code, 403)

    def test_private_inbox_and_read_receipt(self):
        announcement = Announcement.objects.create(text='Salom', audience='test', created_by=self.teacher)
        own = StudentMessage.objects.create(announcement=announcement, student=self.first)
        other = StudentMessage.objects.create(announcement=announcement, student=self.second)
        self.client.logout()
        self.assertEqual(self.client.get('/api/messages/').status_code, 401)
        self.client.post('/auth/login/', json.dumps({'student_id': self.first.student_id}), content_type='application/json')
        self.assertEqual([m['id'] for m in self.client.get('/api/messages/').json()['messages']], [own.pk])
        self.assertEqual(self.client.post(f'/api/messages/{other.pk}/read/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/messages/{own.pk}/read/').status_code, 200)
        own.refresh_from_db()
        self.assertIsNotNone(own.read_at)

    def test_read_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session['student_pk'] = self.first.pk
        session.save()
        announcement = Announcement.objects.create(text='Salom', audience='test')
        own = StudentMessage.objects.create(announcement=announcement, student=self.first)
        self.assertEqual(client.post(f'/api/messages/{own.pk}/read/').status_code, 403)


class CurriculumIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        import io
        call_command('import_curriculum', stdout=io.StringIO())
        cls.teacher = get_user_model().objects.create_superuser('curriculum_teacher', password='test-password')

    def login_student(self, student):
        response = self.client.post('/auth/login/', json.dumps({'student_id': '  ' + student.student_id.lower() + '  '}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_teacher_creation_to_student_site(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('admin:bot_app_student_add'), {'name':'Yangi o‘quvchi', 'book_level':'2B', '_save':'Saqlash'})
        self.assertEqual(response.status_code, 302, response.content[:500])
        student = Student.objects.get(name='Yangi o‘quvchi')
        self.assertTrue(student.student_id.startswith('TOPIK-'))
        self.assertEqual(student.group.book_level, '2B')
        self.client.logout()
        data = self.login_student(student)
        self.assertEqual(data['student']['book_level'], '2B')
        lessons = self.client.get('/api/lessons/').json()['lessons']
        self.assertEqual([l['number'] for l in lessons], list(range(10, 19)))
        detail = self.client.get(f"/api/lessons/{lessons[0]['id']}/").json()
        self.assertTrue(detail['words'])
        self.assertTrue(detail['grammar'])

    def test_same_level_auto_group_and_level_change(self):
        first = Student.objects.create(name='Birinchi', book_level='1A')
        second = Student.objects.create(name='Ikkinchi', book_level='1A')
        self.assertEqual(first.group, second.group)
        old_id = second.student_id
        second.book_level = '2B'
        second.save(update_fields=['book_level'])
        second.refresh_from_db()
        self.assertEqual(second.group.book_level, '2B')
        self.assertEqual(second.student_id, old_id)
        self.assertEqual(StudyGroup.objects.filter(book_level='1A').count(), 1)

    def test_import_idempotent_and_preserves_teacher_edits(self):
        from django.core.management import call_command
        from .models import Vocabulary, Grammar, Lesson
        import io
        self.assertEqual(Vocabulary.objects.filter(source_key__isnull=False).count(), 1702)
        self.assertEqual(Grammar.objects.count(), 135)
        self.assertEqual(Lesson.objects.count(), 34)
        word = Vocabulary.objects.first()
        word.translation = 'Ustoz tahriri'
        word.save()
        call_command('import_curriculum', stdout=io.StringIO())
        word.refresh_from_db()
        self.assertEqual(word.translation, 'Ustoz tahriri')
        self.assertEqual(Vocabulary.objects.filter(source_key__isnull=False).count(), 1702)
        expected = {'1A':(439,32,8), '1B':(378,32,8), '2A':(484,36,9), '2B':(401,35,9)}
        for level, (words, grammar, lessons) in expected.items():
            self.assertEqual(Vocabulary.objects.filter(lesson__book_level=level).count(), words)
            self.assertEqual(Grammar.objects.filter(lesson__book_level=level).count(), grammar)
            self.assertEqual(Lesson.objects.filter(book_level=level).count(), lessons)

    def test_word_and_grammar_progress_shared_with_teacher(self):
        from .models import Vocabulary, Grammar, WordProgress, GrammarProgress
        student = Student.objects.create(name='Mashq', book_level='1A')
        self.login_student(student)
        word = Vocabulary.objects.filter(lesson__book_level='1A').first()
        grammar = Grammar.objects.filter(lesson=word.lesson).first()
        for _ in range(2):
            response = self.client.post(f'/api/words/{word.pk}/progress/', json.dumps({'learned':True}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.client.post(f'/api/grammar/{grammar.pk}/progress/', '{}', content_type='application/json')
        student.refresh_from_db()
        self.assertEqual(student.words_learned, 1)
        self.assertEqual(WordProgress.objects.filter(student=student).count(), 1)
        self.assertEqual(GrammarProgress.objects.filter(student=student).count(), 1)
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('admin:bot_app_student_change', args=[student.pk]))
        self.assertContains(response, '1 ta mashq qilingan, 1 ta yodlangan')
        self.assertContains(response, '1 ta grammatika qoidasi o‘qilgan')

    def test_other_level_and_logged_out_access_denied(self):
        from .models import Lesson, Vocabulary
        self.assertEqual(self.client.get('/api/lessons/').status_code, 401)
        student = Student.objects.create(name='Chegara', book_level='1A')
        self.login_student(student)
        other = Lesson.objects.filter(book_level='2B').first()
        self.assertEqual(self.client.get(f'/api/lessons/{other.pk}/').status_code, 404)
        word = Vocabulary.objects.filter(lesson=other).first()
        self.assertEqual(self.client.post(f'/api/words/{word.pk}/progress/', json.dumps({'learned':True}), content_type='application/json').status_code, 404)
        self.client.post('/auth/logout/')
        self.assertEqual(self.client.get('/auth/me/').status_code, 401)

    def test_bad_login_input_and_disabled_student(self):
        for body in ['null', '[]', '{"student_id":123}', 'bad json']:
            response = self.client.post('/auth/login/', body, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        student = Student.objects.create(name='Nofaol', is_active=False)
        self.assertEqual(self.client.post('/auth/login/', json.dumps({'student_id':student.student_id}), content_type='application/json').status_code, 403)

    def test_student_page_and_admin_theme(self):
        self.assertContains(self.client.get('/'), 'student.css')
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse('admin:index')), 'teacher.css')
        self.assertContains(self.client.get(reverse('admin:index')), '1702 so‘z')
