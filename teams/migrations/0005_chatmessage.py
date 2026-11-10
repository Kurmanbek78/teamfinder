import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0004_seed_skills_by_direction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(blank=True, verbose_name='Сообщение')),
                ('attachment', models.FileField(blank=True, null=True, upload_to='chat_attachments/%Y/%m/', verbose_name='Вложение')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to='teams.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Сообщение чата',
                'verbose_name_plural': 'Сообщения чата',
                'ordering': ['created_at'],
            },
        ),
    ]
