import django.db.models.deletion
from django.db import migrations, models


INITIAL_DIRECTIONS = [
    'Frontend',
    'Backend и API',
    'Мобильная разработка',
    'UI/UX и графический дизайн',
    'Тестирование и QA',
    'Данные и ИИ',
    'DevOps и базы данных',
    'Аналитика, управление проектом и документация',
]


def populate_directions(apps, schema_editor):
    Direction = apps.get_model('teams', 'Direction')
    Skill = apps.get_model('teams', 'Skill')
    Profile = apps.get_model('teams', 'Profile')
    Project = apps.get_model('teams', 'Project')

    dir_map = {}
    for name in INITIAL_DIRECTIONS:
        obj, _ = Direction.objects.get_or_create(name=name)
        dir_map[name] = obj

    for skill in Skill.objects.all():
        lower_name = (skill.name or '').strip().lower()
        if lower_name in ('python', 'django'):
            skill.direction = dir_map['Backend и API']
        elif lower_name in ('design', 'дизайн'):
            skill.direction = dir_map['UI/UX и графический дизайн']
        else:
            other_dir, _ = Direction.objects.get_or_create(name='Прочее')
            skill.direction = other_dir
        skill.save(update_fields=['direction'])

    for profile in Profile.objects.prefetch_related('skills').all():
        dir_ids = {s.direction_id for s in profile.skills.all() if s.direction_id}
        if dir_ids:
            profile.directions.add(*dir_ids)

    for project in Project.objects.prefetch_related('required_skills').all():
        dir_ids = {s.direction_id for s in project.required_skills.all() if s.direction_id}
        if dir_ids:
            project.required_directions.add(*dir_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Direction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Направление')),
            ],
            options={
                'verbose_name': 'Направление',
                'verbose_name_plural': 'Направления',
                'ordering': ['id'],
            },
        ),
        migrations.AlterModelOptions(
            name='skill',
            options={
                'ordering': ['direction__id', 'name'],
                'verbose_name': 'Навык',
                'verbose_name_plural': 'Навыки',
            },
        ),
        migrations.AddField(
            model_name='skill',
            name='direction',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='skills',
                to='teams.direction',
                verbose_name='Направление',
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='directions',
            field=models.ManyToManyField(
                blank=True,
                related_name='profiles',
                to='teams.direction',
                verbose_name='Направления',
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='required_directions',
            field=models.ManyToManyField(
                blank=True,
                related_name='projects',
                to='teams.direction',
                verbose_name='Нужные направления',
            ),
        ),
        migrations.RunPython(populate_directions, migrations.RunPython.noop),
    ]
