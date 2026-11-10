import secrets
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.urls import reverse
from teams.models import (
    StudyGroup,
    Direction,
    Skill,
    Profile,
    Project,
    Application,
    ChatMessage,
    create_notification,
)


class Command(BaseCommand):
    help = 'Добавляет демонстрационные аккаунты с префиксом demo_ и реалистичную активность без изменения существующих данных.'

    def handle(self, *args, **options):
        group_21, _ = StudyGroup.objects.get_or_create(
            name='ИС-21', defaults={'course': 2}
        )
        group_31, _ = StudyGroup.objects.get_or_create(
            name='ИС-31', defaults={'course': 3}
        )

        accounts_spec = [
            {
                'username': 'demo_teacher',
                'email': 'demo_teacher@example.test',
                'role': 'teacher',
                'course': None,
                'group': None,
                'group_status': 'confirmed',
                'bio': 'Преподаватель профильных ИТ-дисциплин, руководитель курсовых и дипломных проектов.',
                'directions': [
                    'Backend и API',
                    'Аналитика, управление проектом и документация',
                ],
                'skills': ['Python', 'Django', 'SQL', 'UML', 'Техническая документация'],
            },
            {
                'username': 'demo_alikhan',
                'email': 'demo_alikhan@example.test',
                'role': 'student',
                'course': 2,
                'group': group_21,
                'group_status': 'confirmed',
                'bio': 'Студент 2 курса, увлекаюсь серверной разработкой на Python/Django и проектированием БД.',
                'directions': ['Backend и API', 'DevOps и базы данных'],
                'skills': ['Python', 'Django', 'REST API', 'PostgreSQL', 'Git'],
            },
            {
                'username': 'demo_ainura',
                'email': 'demo_ainura@example.test',
                'role': 'student',
                'course': 2,
                'group': group_21,
                'group_status': 'confirmed',
                'bio': 'Создаю удобные интерфейсы в Figma и верстаю адаптивные веб-страницы на React и CSS.',
                'directions': ['Frontend', 'UI/UX и графический дизайн'],
                'skills': [
                    'HTML',
                    'CSS',
                    'JavaScript',
                    'React',
                    'Figma',
                    'Дизайн интерфейсов',
                ],
            },
            {
                'username': 'demo_bekzat',
                'email': 'demo_bekzat@example.test',
                'role': 'student',
                'course': 2,
                'group': group_21,
                'group_status': 'pending',
                'bio': 'Интересуюсь обеспечением качества ПО, пишу тест-кейсы и автотесты на Pytest.',
                'directions': [
                    'Тестирование и QA',
                    'Аналитика, управление проектом и документация',
                ],
                'skills': [
                    'Pytest',
                    'Ручное тестирование',
                    'Тест-кейсы',
                    'Тестирование API',
                    'Техническая документация',
                ],
            },
            {
                'username': 'demo_timur',
                'email': 'demo_timur@example.test',
                'role': 'student',
                'course': 3,
                'group': group_31,
                'group_status': 'confirmed',
                'bio': 'Студент 3 курса, разрабатываю кроссплатформенные мобильные приложения и изучаю анализ данных.',
                'directions': ['Мобильная разработка', 'Данные и ИИ'],
                'skills': ['Flutter', 'Kotlin', 'Python', 'Pandas', 'Машинное обучение'],
            },
        ]

        users = {}
        created_credentials = []

        for spec in accounts_spec:
            uname = spec['username']
            user = User.objects.filter(username=uname).first()
            is_new = False
            if user is None:
                is_new = True
                raw_password = secrets.token_urlsafe(9)
                user = User(username=uname, email=spec['email'])
                user.set_password(raw_password)
                user.save()
                created_credentials.append((uname, spec['role'], raw_password))

            profile, prof_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'role': spec['role'],
                    'course': spec['course'],
                    'study_group': spec['group'],
                    'group_status': spec['group_status'],
                    'bio': spec['bio'],
                },
            )
            if is_new and not prof_created:
                profile.role = spec['role']
                profile.course = spec['course']
                profile.study_group = spec['group']
                profile.group_status = spec['group_status']
                profile.bio = spec['bio']
                profile.save()

            dir_objs = list(Direction.objects.filter(name__in=spec['directions']))
            if dir_objs:
                profile.directions.add(*dir_objs)
            skill_objs = list(Skill.objects.filter(name__in=spec['skills']))
            if skill_objs:
                profile.skills.add(*skill_objs)

            users[uname] = user

        teacher = users['demo_teacher']
        alikhan = users['demo_alikhan']
        ainura = users['demo_ainura']
        bekzat = users['demo_bekzat']
        timur = users['demo_timur']

        if group_21.curator_id is None:
            group_21.curator = teacher
            group_21.save(update_fields=['curator'])

        # 1. Одобренный проект с открытым набором (2 курс, 1 из 2 мест занято)
        proj_schedule, _ = Project.objects.get_or_create(
            owner=alikhan,
            title='Интерактивное расписание и карта кабинетов колледжа',
            defaults={
                'description': (
                    'Веб-сервис для студентов и преподавателей с удобным расписанием занятий, '
                    'фильтрацией по учебным группам и поиском свободных аудиторий по корпусам.'
                ),
                'max_members': 2,
                'status': 'open',
                'moderation_status': 'approved',
            },
        )
        proj_schedule.required_directions.add(
            *Direction.objects.filter(
                name__in=['Frontend', 'Backend и API', 'UI/UX и графический дизайн']
            )
        )
        proj_schedule.required_skills.add(
            *Skill.objects.filter(
                name__in=['Python', 'Django', 'React', 'Figma', 'PostgreSQL']
            )
        )

        # 2. Одобренный проект с открытым набором (3 курс)
        proj_mobile, _ = Project.objects.get_or_create(
            owner=timur,
            title='Мобильный помощник первокурсника с ИИ-навигацией',
            defaults={
                'description': (
                    'Мобильное приложение на Flutter с ответами на частые вопросы студентов, '
                    'календарём сессии и рекомендациями учебных материалов.'
                ),
                'max_members': 3,
                'status': 'open',
                'moderation_status': 'approved',
            },
        )
        proj_mobile.required_directions.add(
            *Direction.objects.filter(
                name__in=['Мобильная разработка', 'Данные и ИИ']
            )
        )
        proj_mobile.required_skills.add(
            *Skill.objects.filter(
                name__in=['Flutter', 'Kotlin', 'Python', 'Машинное обучение']
            )
        )

        # 3. Одобренный проект с заполненными местами (2 курс, 1 из 1 место занято -> закрыт)
        proj_full, _ = Project.objects.get_or_create(
            owner=ainura,
            title='Веб-панель учёта лабораторных и практических работ',
            defaults={
                'description': (
                    'Сервис для отслеживания дедлайнов по лабораторным работам, чек-листов '
                    'проверки и статистики успеваемости учебной группы.'
                ),
                'max_members': 1,
                'status': 'closed',
                'moderation_status': 'approved',
            },
        )
        proj_full.required_directions.add(
            *Direction.objects.filter(
                name__in=['Backend и API', 'Frontend']
            )
        )
        proj_full.required_skills.add(
            *Skill.objects.filter(
                name__in=['Python', 'REST API', 'JavaScript', 'SQLite']
            )
        )

        # 4. Проект на проверке у преподавателя (2 курс)
        proj_pending, _ = Project.objects.get_or_create(
            owner=bekzat,
            title='Тренажёр автоматической проверки SQL-запросов',
            defaults={
                'description': (
                    'Платформа с практическими заданиями по реляционным базам данных '
                    'и автоматическим запуском проверочных тест-кейсов.'
                ),
                'max_members': 2,
                'status': 'open',
                'moderation_status': 'pending',
            },
        )
        proj_pending.required_directions.add(
            *Direction.objects.filter(
                name__in=['Backend и API', 'Тестирование и QA', 'DevOps и базы данных']
            )
        )
        proj_pending.required_skills.add(
            *Skill.objects.filter(
                name__in=['Python', 'SQL', 'PostgreSQL', 'Pytest', 'Docker']
            )
        )

        # Заявки (все между студентами одного курса — 2 курса)
        app_ainura_sched, _ = Application.objects.get_or_create(
            project=proj_schedule,
            applicant=ainura,
            defaults={
                'message': 'Разработаю дизайн-систему в Figma и сверстаю адаптивные страницы расписания на React.',
                'status': 'accepted',
            },
        )
        app_bekzat_sched, _ = Application.objects.get_or_create(
            project=proj_schedule,
            applicant=bekzat,
            defaults={
                'message': 'Готов написать автотесты на Pytest для API расписания и оформить документацию.',
                'status': 'pending',
            },
        )
        app_alikhan_full, _ = Application.objects.get_or_create(
            project=proj_full,
            applicant=alikhan,
            defaults={
                'message': 'Возьму на себя разработку серверной части и моделей базы данных.',
                'status': 'accepted',
            },
        )
        app_bekzat_full, _ = Application.objects.get_or_create(
            project=proj_full,
            applicant=bekzat,
            defaults={
                'message': 'Хочу подключиться к тестированию пользовательских сценариев.',
                'status': 'rejected',
            },
        )

        proj_schedule.sync_recruitment_status()
        proj_full.sync_recruitment_status()

        # Сообщения в командном чате Проекта 1 (proj_schedule)
        chat_texts_schedule = [
            (
                alikhan,
                'Привет! Рад работать вместе. Я уже подготовил структуру БД для расписания и учебных корпусов.',
            ),
            (
                ainura,
                'Привет! Отлично, я собрала макет главной страницы и карточки аудиторий в Figma, скоро перенесу в вёрстку.',
            ),
            (
                alikhan,
                'Супер! Тогда я сегодня добавлю фильтрацию расписания по номеру группы и дню недели.',
            ),
        ]
        last_msg_schedule = None
        for author, text in chat_texts_schedule:
            msg, _ = ChatMessage.objects.get_or_create(
                project=proj_schedule,
                author=author,
                text=text,
            )
            last_msg_schedule = msg

        # Сообщения в командном чате Проекта 3 (proj_full)
        chat_texts_full = [
            (
                ainura,
                'Привет! Команда собрана, давай согласуем поля карточки лабораторной работы.',
            ),
            (
                alikhan,
                'Привет! Предлагаю хранить предмет, дедлайн, ссылку на репозиторий и статус проверки.',
            ),
        ]
        for author, text in chat_texts_full:
            ChatMessage.objects.get_or_create(
                project=proj_full,
                author=author,
                text=text,
            )

        # Уведомления (идемпотентно по event_key)
        create_notification(
            recipient=teacher,
            message=f'Новый проект на проверку: «{proj_pending.title}» от {bekzat.username}.',
            link=reverse('project_detail', args=[proj_pending.pk]),
            event_key=f'project_pending:{proj_pending.pk}',
        )
        create_notification(
            recipient=alikhan,
            message=f'Ваш проект «{proj_schedule.title}» одобрен преподавателем и опубликован в каталоге.',
            link=reverse('project_detail', args=[proj_schedule.pk]),
            event_key=f'proj_mod:{proj_schedule.pk}:approved',
        )
        create_notification(
            recipient=alikhan,
            message=f'Новая заявка на проект «{proj_schedule.title}» от {bekzat.username}.',
            link=reverse('project_detail', args=[proj_schedule.pk]),
            event_key=f'app_new:{app_bekzat_sched.pk}',
        )
        create_notification(
            recipient=alikhan,
            message=f'Ваша заявка на проект «{proj_full.title}» принята!',
            link=reverse('project_detail', args=[proj_full.pk]),
            event_key=f'app_status:{app_alikhan_full.pk}:accepted',
        )
        create_notification(
            recipient=ainura,
            message=f'Ваша заявка на проект «{proj_schedule.title}» принята!',
            link=reverse('project_detail', args=[proj_schedule.pk]),
            event_key=f'app_status:{app_ainura_sched.pk}:accepted',
        )
        if last_msg_schedule:
            create_notification(
                recipient=ainura,
                message=f'Новое сообщение от {alikhan.username} в командном чате проекта «{proj_schedule.title}».',
                link=reverse('project_chat', args=[proj_schedule.pk]),
                event_key=f'chat_msg:{last_msg_schedule.pk}:{ainura.id}',
            )
        create_notification(
            recipient=bekzat,
            message=f'Ваша заявка на проект «{proj_full.title}» отклонена.',
            link=reverse('project_detail', args=[proj_full.pk]),
            event_key=f'app_status:{app_bekzat_full.pk}:rejected',
        )
        create_notification(
            recipient=timur,
            message=f'Ваш проект «{proj_mobile.title}» одобрен преподавателем и опубликован в каталоге.',
            link=reverse('project_detail', args=[proj_mobile.pk]),
            event_key=f'proj_mod:{proj_mobile.pk}:approved',
        )

        self.stdout.write(self.style.SUCCESS('Демо-данные успешно подготовлены.'))
        if created_credentials:
            self.stdout.write('Созданные демо-аккаунты (сохраните пароли, повторно они не выводятся):')
            for uname, role, pw in created_credentials:
                self.stdout.write(f'  {uname} ({role}): {pw}')
        else:
            self.stdout.write('Все demo_ аккаунты уже существовали, их пароли не изменялись.')
