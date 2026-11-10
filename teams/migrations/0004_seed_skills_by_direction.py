from django.db import migrations


STARTER_SKILLS = {
    'Frontend': [
        'HTML',
        'CSS',
        'JavaScript',
        'TypeScript',
        'React',
    ],
    'Backend и API': [
        'Python',
        'Django',
        'Flask',
        'REST API',
        'SQL',
    ],
    'Мобильная разработка': [
        'Kotlin',
        'Java',
        'Swift',
        'Flutter',
        'React Native',
    ],
    'UI/UX и графический дизайн': [
        'Figma',
        'Прототипирование',
        'Дизайн интерфейсов',
        'Графический дизайн',
    ],
    'Тестирование и QA': [
        'Ручное тестирование',
        'Тест-кейсы',
        'Pytest',
        'Тестирование API',
        'Selenium',
    ],
    'Данные и ИИ': [
        'Анализ данных',
        'Pandas',
        'NumPy',
        'Визуализация данных',
        'Машинное обучение',
    ],
    'DevOps и базы данных': [
        'Git',
        'PostgreSQL',
        'SQLite',
        'Docker',
        'Linux',
        'CI/CD',
    ],
    'Аналитика, управление проектом и документация': [
        'Анализ требований',
        'UML',
        'Планирование проекта',
        'Техническая документация',
    ],
}


def seed_starter_skills(apps, schema_editor):
    Direction = apps.get_model('teams', 'Direction')
    Skill = apps.get_model('teams', 'Skill')

    for dir_name, skill_names in STARTER_SKILLS.items():
        direction, _ = Direction.objects.get_or_create(name=dir_name)
        for s_name in skill_names:
            existing = Skill.objects.filter(name__iexact=s_name).first()
            if existing:
                if existing.direction_id != direction.id:
                    existing.direction = direction
                    existing.save(update_fields=['direction'])
            else:
                Skill.objects.create(name=s_name, direction=direction)

    # Убедимся, что существующий навык «Дизайн» или «Design» также привязан к UI/UX
    ui_dir = Direction.objects.filter(name='UI/UX и графический дизайн').first()
    if ui_dir:
        Skill.objects.filter(name__in=['Дизайн', 'дизайн', 'Design', 'design']).update(
            direction=ui_dir
        )


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0003_courses_groups_roles_moderation'),
    ]

    operations = [
        migrations.RunPython(seed_starter_skills, migrations.RunPython.noop),
    ]
