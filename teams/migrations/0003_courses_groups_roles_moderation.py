import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


INITIAL_GROUPS = [
    ('ИС-11', 1),
    ('ИС-21', 2),
    ('ИС-31', 3),
    ('ИС-41', 4),
]


def migrate_roles_groups_and_projects(apps, schema_editor):
    StudyGroup = apps.get_model('teams', 'StudyGroup')
    Profile = apps.get_model('teams', 'Profile')
    Project = apps.get_model('teams', 'Project')

    for name, course in INITIAL_GROUPS:
        StudyGroup.objects.get_or_create(name=name, defaults={'course': course})

    Profile.objects.filter(role__in=('author', 'member')).update(role='student')
    Project.objects.all().update(moderation_status='approved')


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0002_direction_and_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Учебная группа')),
                ('course', models.PositiveSmallIntegerField(choices=[(1, '1 курс'), (2, '2 курс'), (3, '3 курс'), (4, '4 курс')], default=1, verbose_name='Курс')),
                ('curator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='curated_groups', to=settings.AUTH_USER_MODEL, verbose_name='Куратор')),
            ],
            options={
                'verbose_name': 'Учебная группа',
                'verbose_name_plural': 'Учебные группы',
                'ordering': ['course', 'name'],
            },
        ),
        migrations.AddField(
            model_name='profile',
            name='course',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, '1 курс'), (2, '2 курс'), (3, '3 курс'), (4, '4 курс')], null=True, verbose_name='Курс'),
        ),
        migrations.AddField(
            model_name='profile',
            name='group_status',
            field=models.CharField(choices=[('pending', 'Ожидает подтверждения'), ('confirmed', 'Подтверждена')], default='pending', max_length=15, verbose_name='Статус группы'),
        ),
        migrations.AddField(
            model_name='profile',
            name='study_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='teams.studygroup', verbose_name='Учебная группа'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='role',
            field=models.CharField(choices=[('student', 'Студент'), ('teacher', 'Преподаватель'), ('admin', 'Администратор')], default='student', max_length=15, verbose_name='Роль'),
        ),
        migrations.AddField(
            model_name='project',
            name='max_members',
            field=models.PositiveIntegerField(blank=True, help_text='Не включая автора. Оставьте пустым, если лимит не задан.', null=True, verbose_name='Количество мест для участников'),
        ),
        migrations.AddField(
            model_name='project',
            name='moderation_status',
            field=models.CharField(choices=[('pending', 'На проверке'), ('approved', 'Одобрен'), ('rejected', 'Отклонён')], default='approved', max_length=15, verbose_name='Статус модерации'),
        ),
        migrations.AddField(
            model_name='project',
            name='rejection_reason',
            field=models.TextField(blank=True, verbose_name='Причина отклонения'),
        ),
        migrations.RunPython(migrate_roles_groups_and_projects, migrations.RunPython.noop),
    ]
