from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import StudyGroup, Student


class DashboardActionsTests(TestCase):
    def setUp(self):
        self.teacher = get_user_model().objects.create_superuser('dashboard_teacher', password='test-password')
        self.client.force_login(self.teacher)

    def test_dashboard_exposes_all_primary_add_actions(self):
        response = self.client.get(reverse('admin:index'))
        for model in ('student','studygroup','lesson','vocabulary','grammar','grammarexercise','exam','examquestion','announcement'):
            self.assertContains(response, reverse(f'admin:bot_app_{model}_add'))
        self.assertContains(response, 'Tezkor qo‘shish')
        self.assertContains(response, 'dashboard.css')

    def test_group_setup_keeps_single_group_and_members(self):
        student = Student.objects.create(name='Guruh o‘quvchisi', book_level='1A')
        original_group = student.group_id
        count = StudyGroup.objects.count()
        response = self.client.post(reverse('admin:bot_app_studygroup_add'), {'name':'Tonggi 1A','book_level':'1A','notes':'Yangi nom'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StudyGroup.objects.count(), count)
        student.refresh_from_db()
        self.assertEqual(student.group_id, original_group)
        self.assertEqual(student.group.name, 'Tonggi 1A')

    def test_readonly_staff_has_no_quick_add_buttons(self):
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user('readonly_teacher', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_student', content_type__app_label='bot_app'))
        self.client.force_login(staff)
        response=self.client.get(reverse('admin:index'))
        self.assertNotContains(response, 'class="quick-add-card"')
        self.assertEqual(self.client.post(reverse('admin:bot_app_studygroup_add'), {'name':'X','book_level':'1A'}).status_code,403)
