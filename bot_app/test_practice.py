import io
import json
from unittest.mock import patch, MagicMock
from urllib.error import URLError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Student, GrammarExercise, PracticeAttempt
from .services.gemini import analyze, AIUnavailable


class PracticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('import_curriculum', stdout=io.StringIO())
        call_command('import_exercises', stdout=io.StringIO())
        cls.student = Student.objects.create(name='Mashq o‘quvchi', book_level='1A')
        cls.teacher = get_user_model().objects.create_superuser('practice_teacher', password='test-password')

    def setUp(self):
        cache.clear()
        session = self.client.session
        session['student_pk'] = self.student.pk
        session.save()

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def start(self):
        response = self.post('/api/practice/start/', {})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def finish(self):
        body = self.start()
        attempt = PracticeAttempt.objects.get(pk=body['id'])
        answers = {str(i):q['correct_index'] for i,q in enumerate(attempt.questions)}
        response = self.post(f'/api/practice/{attempt.pk}/submit/', {'answers':answers})
        self.assertEqual(response.status_code, 200)
        return attempt, answers, response.json()

    def test_exact_book_level_and_no_answer_leak(self):
        for level, count in [('1A',8),('1B',8),('2A',9),('2B',9)]:
            self.student.book_level = level
            self.student.save()
            data = self.start()
            self.assertEqual(data['book_level'], level)
            self.assertEqual(len(data['questions']), count)
            for q in data['questions']:
                self.assertNotIn('correct_index', q)
                self.assertNotIn('explanation', q)
                self.assertEqual(q['sentence'].count('___'), 1)
            attempt = PracticeAttempt.objects.get(pk=data['id'])
            for q in attempt.questions:
                self.assertEqual(GrammarExercise.objects.get(pk=q['exercise_id']).grammar.lesson.book_level, level)

    def test_score_saved_once_and_question_snapshot_preserved(self):
        attempt, answers, data = self.finish()
        self.assertEqual(data['percentage'], 100)
        self.assertEqual(data['score'], data['total'])
        self.post(f'/api/practice/{attempt.pk}/submit/', {'answers':answers})
        self.student.refresh_from_db()
        self.assertEqual(self.student.tests_completed, 1)
        GrammarExercise.objects.update(explanation='Changed after test')
        response = self.post(f'/api/practice/{attempt.pk}/submit/', {'answers':answers})
        self.assertEqual(response.json()['review'], data['review'])

    def test_reject_missing_bad_and_bool_answers(self):
        data = self.start()
        for answers in [{}, [], {'0':99}, {'0':True}, None]:
            self.assertEqual(self.post(f"/api/practice/{data['id']}/submit/", {'answers':answers}).status_code, 400)
        attempt = PracticeAttempt.objects.get(pk=data['id'])
        self.assertIsNone(attempt.completed_at)

    def test_wrong_owner_and_wrong_level_rejected(self):
        data = self.start()
        attempt = PracticeAttempt.objects.get(pk=data['id'])
        answers = {str(i):q['correct_index'] for i,q in enumerate(attempt.questions)}
        self.student.book_level = '2B'
        self.student.save()
        self.assertEqual(self.post(f'/api/practice/{attempt.pk}/submit/', {'answers':answers}).status_code, 409)
        other = Student.objects.create(name='Other')
        session = self.client.session
        session['student_pk'] = other.pk
        session.save()
        self.assertEqual(self.post(f'/api/practice/{attempt.pk}/submit/', {'answers':answers}).status_code, 404)
        self.assertEqual(self.post(f'/api/practice/{attempt.pk}/ai/', {}).status_code, 404)

    @override_settings(GEMINI_API_KEY='')
    def test_missing_ai_does_not_break_results(self):
        attempt, _, data = self.finish()
        self.assertFalse(data['ai_available'])
        response = self.post(f'/api/practice/{attempt.pk}/ai/', {})
        self.assertEqual(response.status_code, 503)
        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.completed_at)
        self.assertEqual(attempt.score, len(attempt.questions))

    @patch('bot_app.practice_views.analyze')
    def test_ai_cached_and_no_personal_identifiers_sent(self, mocked):
        mocked.return_value={'text':'Yaxshi natija. Qoidani takrorlang.','model':'test-model'}
        attempt, _, _ = self.finish()
        for _ in range(2):
            self.assertEqual(self.post(f'/api/practice/{attempt.pk}/ai/', {}).status_code, 200)
        mocked.assert_called_once()
        payload = json.dumps(mocked.call_args.args[0], ensure_ascii=False)
        self.assertNotIn(self.student.student_id, payload)
        self.assertNotIn(self.student.name, payload)
        attempt.refresh_from_db()
        self.assertEqual(attempt.ai_analysis, mocked.return_value['text'])

    def test_exercise_import_idempotent_and_all_lessons_covered(self):
        call_command('import_exercises', stdout=io.StringIO())
        self.assertEqual(GrammarExercise.objects.count(), 34)
        self.assertEqual(GrammarExercise.objects.values('grammar__lesson').distinct().count(), 34)
        for exercise in GrammarExercise.objects.all():
            exercise.full_clean()

    def test_teacher_can_edit_options_and_see_result(self):
        attempt, _, _ = self.finish()
        self.client.force_login(self.teacher)
        exercise = GrammarExercise.objects.first()
        self.assertEqual(self.client.get(reverse('admin:bot_app_grammarexercise_change', args=[exercise.pk])).status_code, 200)
        response = self.client.get(reverse('admin:bot_app_practiceattempt_change', args=[attempt.pk]))
        self.assertContains(response, 'Javoblar tahlili')
        form_data={'grammar':exercise.grammar_id,'sentence':'학교___ 가요.','translation':'Maktabga boraman.',
                   'option_a':'에','option_b':'에서','option_c':'','option_d':'','answer':'0',
                   'explanation':'Joy yo‘nalishi.', 'is_active':'on','_save':'Saqlash'}
        url=reverse('admin:bot_app_grammarexercise_change', args=[exercise.pk])
        self.assertEqual(self.client.post(url, form_data).status_code, 302)
        form_data['option_b']='에'
        response=self.client.post(url, form_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Variantlar takrorlanmasin.')


@override_settings(GEMINI_API_KEY='test-secret-not-real', GEMINI_MODEL='primary-model', GEMINI_FALLBACK_MODEL='backup-model', GEMINI_FALLBACK_API_KEY='backup-secret-not-real')
class GeminiAdapterTests(TestCase):
    def response(self, text='Tavsiya'):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':text}]}}]}).encode()
        return response

    @patch('bot_app.services.gemini.urlopen')
    def test_primary_timeout_uses_backup_and_header_auth(self, mocked):
        mocked.side_effect=[TimeoutError(),self.response()]
        result=analyze({'book_level':'1A','correct':2,'total':3})
        self.assertEqual(result['model'],'backup-model')
        self.assertEqual(mocked.call_count,2)
        for call in mocked.call_args_list:
            req=call.args[0]
            self.assertNotIn('secret',req.full_url)
            self.assertTrue(req.has_header('X-goog-api-key'))

    @patch('bot_app.services.gemini.urlopen')
    def test_both_fail_safe_error(self, mocked):
        mocked.side_effect=URLError('private diagnostic test-secret-not-real')
        with self.assertRaises(AIUnavailable) as error:
            analyze({'book_level':'1B'})
        self.assertNotIn('test-secret',str(error.exception))
        self.assertEqual(mocked.call_count,2)

    @patch('bot_app.services.gemini.urlopen')
    def test_empty_response_uses_fallback(self, mocked):
        mocked.side_effect=[self.response(''),self.response('Zaxira javob')]
        self.assertEqual(analyze({})['text'],'Zaxira javob')
