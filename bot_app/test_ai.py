import json
from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase, override_settings
from .models import Student, Lesson, Grammar, PracticeAttempt
from .services.gemini import AIUnavailable


class StudentAITests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = Student.objects.create(name='AI student', book_level='1A')
        self.lesson = Lesson.objects.create(book_level='1A', number=1, title='Salom')
        self.other = Lesson.objects.create(book_level='2B', number=1, title='Other')
        Grammar.objects.create(lesson=self.lesson, title='입니다', explanation='Hurmat shakli')
        session = self.client.session
        session['student_pk'] = self.student.pk
        session.save()

    def post(self, path, **data):
        return self.client.post(path, json.dumps(data), content_type='application/json')

    def generated(self):
        return {'text': json.dumps({'questions': [dict(sentence=f'{i} 저는 학생___', translation='Men talabaman', rule='입니다', options=['입니다', '갑니다', '옵니다', '먹어요'], correct_index=0, explanation='Ot bilan ishlatiladi') for i in range(5)]}), 'model': 'test'}

    @patch('bot_app.ai_views.generate')
    def test_generated_test_scored_and_private(self, generate):
        generate.return_value = self.generated()
        response = self.post('/api/ai/test/', lesson_id=self.lesson.pk)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for q in body['questions']:
            self.assertNotIn('correct_index', q)
            self.assertNotIn('explanation', q)
        url = f"/api/practice/{body['id']}/submit/"
        result = self.post(url, answers={str(i): 0 for i in range(5)})
        self.assertEqual(result.json()['score'], 5)
        self.post(url, answers={str(i): 0 for i in range(5)})
        self.student.refresh_from_db()
        self.assertEqual(self.student.tests_completed, 1)
        other = Student.objects.create(name='Other', book_level='1A')
        session = self.client.session
        session['student_pk'] = other.pk
        session.save()
        self.assertEqual(self.post(url, answers={}).status_code, 404)

    @patch('bot_app.ai_views.generate')
    def test_bad_output_not_saved(self, generate):
        data = self.generated()
        questions = json.loads(data['text'])
        questions['questions'][0]['correct_index'] = True
        data['text'] = json.dumps(questions)
        generate.return_value = data
        self.assertEqual(self.post('/api/ai/test/', lesson_id=self.lesson.pk).status_code, 503)
        self.assertEqual(PracticeAttempt.objects.count(), 0)

    @patch('bot_app.ai_views.generate')
    def test_scope_auth_validation_and_limits(self, generate):
        generate.return_value = {'text': 'Salom!', 'model': 'test'}
        self.assertEqual(self.post('/api/ai/tutor/', lesson_id=self.other.pk, message='Salom').status_code, 404)
        self.assertEqual(self.post('/api/ai/tutor/', lesson_id=self.lesson.pk, message=['bad']).status_code, 400)
        self.assertEqual(self.post('/api/ai/tutor/', lesson_id=self.lesson.pk, message='Salom').status_code, 200)
        evidence = generate.call_args.args[1]
        self.assertNotIn('student_id', evidence)
        self.assertNotIn('name', evidence)
        self.assertEqual(self.post('/api/ai/tutor/', lesson_id=self.lesson.pk, message='Yana').status_code, 429)
        self.client.logout()
        self.assertEqual(self.post('/api/ai/test/', lesson_id=self.lesson.pk).status_code, 401)

    @override_settings(GEMINI_API_KEY='')
    def test_missing_key_is_recoverable(self):
        self.assertEqual(self.post('/api/ai/test/', lesson_id=self.lesson.pk).status_code, 503)
        self.assertEqual(self.post('/api/ai/tutor/', lesson_id=self.lesson.pk, mode='lesson').status_code, 503)

    @patch('bot_app.services.gemini.generate')
    def test_teacher_draft_permission_and_escaped_output(self, generate):
        from django.contrib.auth import get_user_model
        teacher = get_user_model().objects.create_superuser('ai_teacher', password='test-password')
        self.client.force_login(teacher)
        generate.return_value = {'text': '<script>bad()</script> Dars rejasi', 'model': 'test'}
        response = self.client.post('/admin/bot_app/lesson/ai-draft/', {'book_level': '1A', 'topic': 'Salomlashish'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(Lesson.objects.count(), 2)
        teacher.is_superuser = False
        teacher.save()
        self.assertEqual(self.client.get('/admin/bot_app/lesson/ai-draft/').status_code, 403)


class AISettingsTests(TestCase):
    def test_local_key_overrides_stale_reloader_environment(self):
        import config.settings as config
        with patch.object(config, 'DEBUG', True), patch.object(config, 'LOCAL_ENV', {'GEMINI_API_KEY': 'new-test-key'}), patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            self.assertEqual(config.ai_setting('GEMINI_API_KEY'), 'new-test-key')

    def test_production_environment_has_priority(self):
        import config.settings as config
        with patch.object(config, 'DEBUG', False), patch.object(config, 'LOCAL_ENV', {'GEMINI_API_KEY': 'local-test-key'}), patch.dict('os.environ', {'GEMINI_API_KEY': 'deployment-test-key'}):
            self.assertEqual(config.ai_setting('GEMINI_API_KEY'), 'deployment-test-key')
