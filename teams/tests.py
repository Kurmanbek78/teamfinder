import shutil
import tempfile
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from .admin import ProfileAdmin
from .models import StudyGroup, Profile, Project, Application, Skill, ChatMessage, Notification


def make_user(username, role, course=None, study_group=None):
    user = User.objects.create_user(username=username, password='pass12345')
    Profile.objects.create(
        user=user, role=role, course=course, study_group=study_group
    )
    return user


class TeamFinderTests(TestCase):
    def setUp(self):
        self.author = make_user('author1', 'author')
        self.member = make_user('member1', 'member')
        self.skill = Skill.objects.create(name='Python')
        self.project = Project.objects.create(
            owner=self.author, title='Тестовый проект', description='Описание'
        )
        self.project.required_skills.add(self.skill)

    def test_home_shows_open_projects(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый проект')

    def test_author_can_create_project(self):
        self.client.login(username='author1', password='pass12345')
        response = self.client.post(reverse('project_create'), {
            'title': 'Новый проект',
            'description': 'Текст',
            'required_skills': [self.skill.pk],
            'status': 'open',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(title='Новый проект').exists())

    def test_member_cannot_create_project(self):
        self.client.login(username='member1', password='pass12345')
        response = self.client.get(reverse('project_create'))
        self.assertEqual(response.status_code, 403)

    def test_not_owner_cannot_edit_project(self):
        self.client.login(username='member1', password='pass12345')
        response = self.client.get(reverse('project_edit', args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)

    def test_member_can_apply_only_once(self):
        self.client.login(username='member1', password='pass12345')
        url = reverse('project_apply', args=[self.project.pk])
        self.client.post(url, {'message': 'Хочу в команду'})
        self.client.post(url, {'message': 'Ещё раз'})
        self.assertEqual(
            Application.objects.filter(project=self.project, applicant=self.member).count(), 1
        )

    def test_owner_can_accept_application(self):
        application = Application.objects.create(
            project=self.project, applicant=self.member, message='Привет'
        )
        self.client.login(username='author1', password='pass12345')
        self.client.post(reverse('application_decide', args=[application.pk, 'accept']))
        application.refresh_from_db()
        self.assertEqual(application.status, 'accepted')

    def test_api_projects_list(self):
        response = self.client.get(reverse('api_projects'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['title'], 'Тестовый проект')

    def test_api_my_applications_requires_login(self):
        response = self.client.get(reverse('api_my_applications'))
        self.assertIn(response.status_code, (401, 403))

    def test_same_course_application_allowed_and_different_course_blocked(self):
        owner_c2 = make_user('owner_c2', 'student', course=2)
        same_course_student = make_user('stud_c2', 'student', course=2)
        other_course_student = make_user('stud_c3', 'student', course=3)
        project = Project.objects.create(
            owner=owner_c2,
            title='Проект 2 курса',
            description='Только для 2 курса',
            moderation_status='approved',
        )

        # Студент того же курса успешно подаёт заявку
        self.client.login(username='stud_c2', password='pass12345')
        self.client.post(reverse('project_apply', args=[project.pk]), {'message': 'Я со 2 курса'})
        self.assertTrue(
            Application.objects.filter(project=project, applicant=same_course_student).exists()
        )

        # Студент другого курса не может подать заявку ни через веб-форму, ни через API
        self.client.login(username='stud_c3', password='pass12345')
        self.client.post(reverse('project_apply', args=[project.pk]), {'message': 'Я с 3 курса'})
        self.assertFalse(
            Application.objects.filter(project=project, applicant=other_course_student).exists()
        )
        api_resp = self.client.post(
            reverse('api_apply', args=[project.pk]), {'message': 'Через API'}
        )
        self.assertEqual(api_resp.status_code, 403)

    def test_pending_project_hidden_from_catalog_and_api(self):
        student = make_user('creator_s1', 'student', course=1)
        self.client.login(username='creator_s1', password='pass12345')
        self.client.post(reverse('project_create'), {
            'title': 'Проект на модерации',
            'description': 'Ожидает проверки',
            'status': 'open',
        })
        pending_project = Project.objects.get(title='Проект на модерации')
        self.assertEqual(pending_project.moderation_status, 'pending')

        home_resp = self.client.get(reverse('home'))
        self.assertNotContains(home_resp, 'Проект на модерации')

        api_list_resp = self.client.get(reverse('api_projects'))
        titles = [item['title'] for item in api_list_resp.json()]
        self.assertNotIn('Проект на модерации', titles)

        api_detail_resp = self.client.get(
            reverse('api_project_detail', args=[pending_project.pk])
        )
        self.assertEqual(api_detail_resp.status_code, 404)

    def test_teacher_can_approve_and_reject_project_with_reason(self):
        student = make_user('proj_student', 'student', course=2)
        teacher = make_user('teacher1', 'teacher')
        project = Project.objects.create(
            owner=student,
            title='Модерируемый проект',
            description='Описание',
            moderation_status='pending',
        )

        self.client.login(username='teacher1', password='pass12345')

        # Отклонение без указания причины не должно проходить
        self.client.post(
            reverse('project_moderate', args=[project.pk, 'reject']),
            {'rejection_reason': '   '},
        )
        project.refresh_from_db()
        self.assertEqual(project.moderation_status, 'pending')

        # Отклонение с указанием причины
        self.client.post(
            reverse('project_moderate', args=[project.pk, 'reject']),
            {'rejection_reason': 'Уточните стек технологий'},
        )
        project.refresh_from_db()
        self.assertEqual(project.moderation_status, 'rejected')
        self.assertEqual(project.rejection_reason, 'Уточните стек технологий')

        # Одобрение проекта преподавателем
        self.client.post(reverse('project_moderate', args=[project.pk, 'approve']))
        project.refresh_from_db()
        self.assertEqual(project.moderation_status, 'approved')
        self.assertEqual(project.rejection_reason, '')
        self.assertContains(self.client.get(reverse('home')), 'Модерируемый проект')

    def test_student_selects_matching_group_and_admin_confirms(self):
        group_c1, _ = StudyGroup.objects.get_or_create(name='ИС-11', defaults={'course': 1})
        group_c2, _ = StudyGroup.objects.get_or_create(name='ИС-21', defaults={'course': 2})

        # Попытка выбрать группу от другого курса отклоняется формой
        bad_resp = self.client.post(reverse('register'), {
            'username': 'new_stud',
            'email': 'stud@college.edu',
            'course': 1,
            'study_group': group_c2.pk,
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(bad_resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='new_stud').exists())

        # Регистрация с группой соответствующего курса создаёт студента со статусом pending
        ok_resp = self.client.post(reverse('register'), {
            'username': 'new_stud',
            'email': 'stud@college.edu',
            'course': 2,
            'study_group': group_c2.pk,
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(ok_resp.status_code, 302)
        profile = Profile.objects.get(user__username='new_stud')
        self.assertEqual(profile.role, 'student')
        self.assertEqual(profile.course, 2)
        self.assertEqual(profile.study_group, group_c2)
        self.assertEqual(profile.group_status, 'pending')

        # Администратор подтверждает учебную группу
        profile_admin = ProfileAdmin(Profile, AdminSite())
        profile_admin.confirm_groups(None, Profile.objects.filter(pk=profile.pk))
        profile.refresh_from_db()
        self.assertEqual(profile.group_status, 'confirmed')

    def test_spots_auto_close_on_last_accept_and_reopen_on_remove(self):
        owner = make_user('team_lead', 'student', course=3)
        cand1 = make_user('cand1', 'student', course=3)
        cand2 = make_user('cand2', 'student', course=3)
        project = Project.objects.create(
            owner=owner,
            title='Командный проект',
            description='Два места',
            max_members=2,
            status='open',
            moderation_status='approved',
        )
        app1 = Application.objects.create(project=project, applicant=cand1)
        app2 = Application.objects.create(project=project, applicant=cand2)

        self.client.login(username='team_lead', password='pass12345')

        # Принятие первого участника — ещё есть место, набор открыт
        self.client.post(reverse('application_decide', args=[app1.pk, 'accept']))
        project.refresh_from_db()
        self.assertEqual(project.accepted_count(), 1)
        self.assertEqual(project.status, 'open')

        # Принятие последнего участника — места заполнены, набор закрывается автоматически
        self.client.post(reverse('application_decide', args=[app2.pk, 'accept']))
        project.refresh_from_db()
        self.assertEqual(project.accepted_count(), 2)
        self.assertEqual(project.status, 'closed')

        # Удаление участника из команды — место освобождается, набор снова открывается
        self.client.post(reverse('application_decide', args=[app2.pk, 'remove']))
        project.refresh_from_db()
        self.assertEqual(project.accepted_count(), 1)
        self.assertEqual(project.status, 'open')

    def test_team_limit_excludes_project_owner(self):
        owner = make_user('solo_lead', 'student', course=4)
        cand1 = make_user('cand_a', 'student', course=4)
        cand2 = make_user('cand_b', 'student', course=4)
        project = Project.objects.create(
            owner=owner,
            title='Проект на 1 участника',
            description='Лимит без автора',
            max_members=1,
            status='open',
            moderation_status='approved',
        )
        # Автор не занимает место из max_members=1
        self.assertEqual(project.accepted_count(), 0)
        self.assertEqual(project.free_spots(), 1)

        app1 = Application.objects.create(project=project, applicant=cand1)
        app2 = Application.objects.create(project=project, applicant=cand2)

        self.client.login(username='solo_lead', password='pass12345')
        self.client.post(reverse('application_decide', args=[app1.pk, 'accept']))
        project.refresh_from_db()
        self.assertEqual(project.accepted_count(), 1)
        self.assertEqual(project.free_spots(), 0)
        self.assertEqual(project.status, 'closed')

        # Второго участника сверх лимита 1 принять нельзя
        self.client.post(reverse('application_decide', args=[app2.pk, 'accept']))
        app2.refresh_from_db()
        self.assertEqual(app2.status, 'pending')
        self.assertEqual(project.accepted_count(), 1)

    def test_chat_access_for_owner_and_accepted_member(self):
        owner = make_user('chat_owner', 'student', course=2)
        accepted_user = make_user('chat_member', 'student', course=2)
        project = Project.objects.create(
            owner=owner,
            title='Проект с чатом',
            description='Описание',
            moderation_status='approved',
        )
        Application.objects.create(
            project=project, applicant=accepted_user, status='accepted'
        )
        chat_url = reverse('project_chat', args=[project.pk])

        # Автор проекта видит кнопку чата и может отправлять сообщения
        self.client.login(username='chat_owner', password='pass12345')
        detail_resp = self.client.get(reverse('project_detail', args=[project.pk]))
        self.assertContains(detail_resp, 'Командный чат')
        post_resp = self.client.post(chat_url, {'text': 'Привет команде!'})
        self.assertEqual(post_resp.status_code, 302)

        # Принятый участник видит сообщение автора и может ответить
        self.client.login(username='chat_member', password='pass12345')
        get_resp = self.client.get(chat_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Привет команде!')
        self.client.post(chat_url, {'text': 'Готов к работе!'})
        self.assertEqual(ChatMessage.objects.filter(project=project).count(), 2)

    def test_chat_forbidden_for_outsiders_and_revoked_on_member_removal(self):
        owner = make_user('c_owner', 'student', course=2)
        pending_user = make_user('c_pending', 'student', course=2)
        accepted_user = make_user('c_accepted', 'student', course=2)
        outsider = make_user('c_outsider', 'student', course=2)
        project = Project.objects.create(
            owner=owner,
            title='Закрытый чат',
            description='Описание',
            moderation_status='approved',
        )
        Application.objects.create(project=project, applicant=pending_user, status='pending')
        app_acc = Application.objects.create(
            project=project, applicant=accepted_user, status='accepted'
        )
        chat_url = reverse('project_chat', args=[project.pk])

        # Посторонний студент и студент с заявкой на рассмотрении получают 403 и не видят ссылку
        for uname in ('c_outsider', 'c_pending'):
            self.client.login(username=uname, password='pass12345')
            detail_resp = self.client.get(reverse('project_detail', args=[project.pk]))
            self.assertNotContains(detail_resp, 'Командный чат')
            self.assertEqual(self.client.get(chat_url).status_code, 403)
            self.assertEqual(
                self.client.post(chat_url, {'text': 'Попытка'}).status_code, 403
            )

        # После удаления принятого участника из команды доступ к чату сразу прекращается
        self.client.login(username='c_owner', password='pass12345')
        self.client.post(reverse('application_decide', args=[app_acc.pk, 'remove']))

        self.client.login(username='c_accepted', password='pass12345')
        self.assertEqual(self.client.get(chat_url).status_code, 403)

    def test_chat_file_restrictions_and_protected_download(self):
        temp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=temp_media):
            owner = make_user('f_owner', 'student', course=3)
            member = make_user('f_member', 'student', course=3)
            outsider = make_user('f_outsider', 'student', course=3)
            project = Project.objects.create(
                owner=owner,
                title='Файловый проект',
                description='Описание',
                moderation_status='approved',
            )
            Application.objects.create(project=project, applicant=member, status='accepted')
            chat_url = reverse('project_chat', args=[project.pk])

            self.client.login(username='f_owner', password='pass12345')

            # 1. Запрещённое расширение (.exe) отклоняется
            bad_ext = SimpleUploadedFile('malware.exe', b'binarydata', content_type='application/octet-stream')
            resp_ext = self.client.post(chat_url, {'text': 'Файл', 'attachment': bad_ext})
            self.assertEqual(resp_ext.status_code, 200)
            self.assertEqual(ChatMessage.objects.filter(project=project).count(), 0)

            # 2. Файл больше 10 МБ отклоняется
            too_big = SimpleUploadedFile('big.pdf', b'a' * (10 * 1024 * 1024 + 10), content_type='application/pdf')
            resp_big = self.client.post(chat_url, {'text': 'Большой PDF', 'attachment': too_big})
            self.assertEqual(resp_big.status_code, 200)
            self.assertEqual(ChatMessage.objects.filter(project=project).count(), 0)

            # 3. Разрешённый проектный формат (.pdf <= 10 МБ) сохраняется
            valid_file = SimpleUploadedFile('spec.pdf', b'%PDF-1.4 content', content_type='application/pdf')
            resp_ok = self.client.post(chat_url, {'text': 'ТЗ проекта', 'attachment': valid_file})
            self.assertEqual(resp_ok.status_code, 302)
            msg = ChatMessage.objects.get(project=project)
            dl_url = reverse('chat_attachment_download', args=[msg.pk])

            # 4. Принятый участник может скачать вложение
            self.client.login(username='f_member', password='pass12345')
            dl_resp = self.client.get(dl_url)
            self.assertEqual(dl_resp.status_code, 200)
            self.assertIn('attachment', dl_resp.get('Content-Disposition', ''))
            list(dl_resp.streaming_content)
            dl_resp.close()

            # 5. Посторонний пользователь получает 403 при попытке скачать файл
            self.client.login(username='f_outsider', password='pass12345')
            self.assertEqual(self.client.get(dl_url).status_code, 403)

    def test_notifications_created_for_key_events_and_no_duplicates(self):
        teacher = make_user('n_teacher', 'teacher')
        owner = make_user('n_owner', 'student', course=2)
        applicant = make_user('n_applicant', 'student', course=2)
        group_c2, _ = StudyGroup.objects.get_or_create(name='ИС-21', defaults={'course': 2})
        applicant.profile.study_group = group_c2
        applicant.profile.save()

        # 1. Создание проекта студентом -> уведомление преподавателю
        self.client.login(username='n_owner', password='pass12345')
        self.client.post(reverse('project_create'), {
            'title': 'Проект с уведомлениями',
            'description': 'Описание',
            'status': 'open',
        })
        project = Project.objects.get(title='Проект с уведомлениями')
        self.assertTrue(
            Notification.objects.filter(
                recipient=teacher, event_key=f'project_pending:{project.pk}'
            ).exists()
        )

        # 2. Преподаватель отклоняет проект с причиной -> уведомление автору с причиной
        self.client.login(username='n_teacher', password='pass12345')
        self.client.post(
            reverse('project_moderate', args=[project.pk, 'reject']),
            {'rejection_reason': 'Доработайте описание'},
        )
        reject_notif = Notification.objects.filter(
            recipient=owner, event_key__startswith=f'proj_mod:{project.pk}:rejected:'
        ).first()
        self.assertIsNotNone(reject_notif)
        self.assertIn('Доработайте описание', reject_notif.message)

        # 3. Преподаватель одобряет проект (и повторный POST не создаёт дубликат)
        self.client.post(reverse('project_moderate', args=[project.pk, 'approve']))
        self.client.post(reverse('project_moderate', args=[project.pk, 'approve']))
        self.assertEqual(
            Notification.objects.filter(
                recipient=owner, event_key=f'proj_mod:{project.pk}:approved'
            ).count(),
            1,
        )

        # 4. Подача заявки студентом -> уведомление автору проекта
        self.client.login(username='n_applicant', password='pass12345')
        self.client.post(
            reverse('project_apply', args=[project.pk]), {'message': 'Возьмите в команду'}
        )
        app = Application.objects.get(project=project, applicant=applicant)
        self.assertTrue(
            Notification.objects.filter(
                recipient=owner, event_key=f'app_new:{app.pk}'
            ).exists()
        )

        # 5. Автор принимает заявку -> уведомление кандидату
        self.client.login(username='n_owner', password='pass12345')
        self.client.post(reverse('application_decide', args=[app.pk, 'accept']))
        self.assertEqual(
            Notification.objects.filter(
                recipient=applicant, event_key=f'app_status:{app.pk}:accepted'
            ).count(),
            1,
        )

        # 6. Сообщение в командном чате -> уведомление другому участнику, но не автору сообщения
        self.client.post(
            reverse('project_chat', args=[project.pk]), {'text': 'Добро пожаловать!'}
        )
        msg = ChatMessage.objects.get(project=project)
        self.assertTrue(
            Notification.objects.filter(
                recipient=applicant, event_key=f'chat_msg:{msg.pk}:{applicant.id}'
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=owner, event_key__startswith=f'chat_msg:{msg.pk}:'
            ).exists()
        )

        # 7. Подтверждение учебной группы администратором (без дубликатов при повторном вызове)
        profile_admin = ProfileAdmin(Profile, AdminSite())
        profile_admin.confirm_groups(None, Profile.objects.filter(pk=applicant.profile.pk))
        profile_admin.confirm_groups(None, Profile.objects.filter(pk=applicant.profile.pk))
        self.assertEqual(
            Notification.objects.filter(
                recipient=applicant,
                event_key=f'group_confirmed:{applicant.profile.pk}:{group_c2.id}',
            ).count(),
            1,
        )

    def test_notifications_isolation_and_mark_read(self):
        user1 = make_user('u_notif1', 'student', course=1)
        user2 = make_user('u_notif2', 'student', course=1)
        n1 = Notification.objects.create(
            recipient=user1, message='Личное уведомление 1', link='/'
        )
        n2 = Notification.objects.create(
            recipient=user1, message='Личное уведомление 2', link='/'
        )
        n_other = Notification.objects.create(
            recipient=user2, message='Чужое секретное уведомление', link='/'
        )

        self.client.login(username='u_notif1', password='pass12345')

        # Пользователь видит только свои уведомления и счётчик непрочитанных
        list_resp = self.client.get(reverse('notifications_list'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'Личное уведомление 1')
        self.assertNotContains(list_resp, 'Чужое секретное уведомление')
        self.assertEqual(list_resp.context['unread_notifications_count'], 2)

        # Нельзя отметить чужое уведомление прочитанным (404)
        bad_mark = self.client.post(reverse('notification_mark_read', args=[n_other.pk]))
        self.assertEqual(bad_mark.status_code, 404)
        n_other.refresh_from_db()
        self.assertFalse(n_other.is_read)

        # Отметка одного своего уведомления прочитанным
        ok_mark = self.client.post(reverse('notification_mark_read', args=[n1.pk]))
        self.assertEqual(ok_mark.status_code, 302)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)

        # Отметка всех своих уведомлений прочитанными
        self.client.post(reverse('notifications_mark_all_read'))
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)
        self.assertEqual(
            Notification.objects.filter(recipient=user1, is_read=False).count(), 0
        )


