import os
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


COURSE_CHOICES = [
    (1, '1 курс'),
    (2, '2 курс'),
    (3, '3 курс'),
    (4, '4 курс'),
]


class StudyGroup(models.Model):
    name = models.CharField('Учебная группа', max_length=50, unique=True)
    course = models.PositiveSmallIntegerField('Курс', choices=COURSE_CHOICES, default=1)
    curator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='curated_groups',
        verbose_name='Куратор',
    )

    class Meta:
        verbose_name = 'Учебная группа'
        verbose_name_plural = 'Учебные группы'
        ordering = ['course', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_course_display()})'


class Direction(models.Model):
    name = models.CharField('Направление', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Направление'
        verbose_name_plural = 'Направления'
        ordering = ['id']

    def __str__(self):
        return self.name


class SkillManager(models.Manager):
    def create(self, **kwargs):
        name = kwargs.get('name')
        if name:
            existing = self.filter(name__iexact=name).first()
            if existing:
                if 'direction' in kwargs and kwargs['direction'] is not None:
                    existing.direction = kwargs['direction']
                    existing.save(update_fields=['direction'])
                return existing
        return super().create(**kwargs)


class Skill(models.Model):
    name = models.CharField('Навык', max_length=50, unique=True)
    direction = models.ForeignKey(
        Direction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='skills',
        verbose_name='Направление',
    )

    objects = SkillManager()

    class Meta:
        verbose_name = 'Навык'
        verbose_name_plural = 'Навыки'
        ordering = ['direction__id', 'name']

    def save(self, *args, **kwargs):
        if self.direction_id is None:
            lower_name = (self.name or '').strip().lower()
            if lower_name in ('python', 'django'):
                dir_name = 'Backend и API'
            elif lower_name in ('design', 'дизайн'):
                dir_name = 'UI/UX и графический дизайн'
            else:
                dir_name = 'Прочее'
            direction, _ = Direction.objects.get_or_create(name=dir_name)
            self.direction = direction
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Студент'),
        ('teacher', 'Преподаватель'),
        ('admin', 'Администратор'),
    ]
    GROUP_STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждена'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('Роль', max_length=15, choices=ROLE_CHOICES, default='student')
    course = models.PositiveSmallIntegerField(
        'Курс', choices=COURSE_CHOICES, null=True, blank=True
    )
    study_group = models.ForeignKey(
        StudyGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name='Учебная группа',
    )
    group_status = models.CharField(
        'Статус группы',
        max_length=15,
        choices=GROUP_STATUS_CHOICES,
        default='pending',
    )
    bio = models.TextField('О себе', blank=True)
    directions = models.ManyToManyField(
        Direction, verbose_name='Направления', blank=True, related_name='profiles'
    )
    skills = models.ManyToManyField(Skill, verbose_name='Навыки', blank=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def save(self, *args, **kwargs):
        was_confirmed = False
        if self.pk:
            old_status = (
                Profile.objects.filter(pk=self.pk)
                .values_list('group_status', flat=True)
                .first()
            )
            was_confirmed = old_status == 'confirmed'
        if self.study_group_id and self.study_group:
            self.course = self.study_group.course
        super().save(*args, **kwargs)
        if self.group_status == 'confirmed' and not was_confirmed:
            group_label = self.study_group.name if self.study_group else 'группа'
            create_notification(
                recipient=self.user,
                message=f'Администратор подтвердил вашу учебную группу ({group_label}).',
                link=reverse('profile_edit'),
                event_key=f'group_confirmed:{self.pk}:{self.study_group_id}',
            )

    def __str__(self):
        return self.user.username


class Project(models.Model):
    STATUS_CHOICES = [
        ('open', 'Набор открыт'),
        ('closed', 'Набор закрыт'),
    ]
    MODERATION_CHOICES = [
        ('pending', 'На проверке'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонён'),
    ]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField('Название', max_length=150)
    description = models.TextField('Описание')
    required_directions = models.ManyToManyField(
        Direction, verbose_name='Нужные направления', blank=True, related_name='projects'
    )
    required_skills = models.ManyToManyField(Skill, verbose_name='Нужные навыки', blank=True)
    max_members = models.PositiveIntegerField(
        'Количество мест для участников',
        null=True,
        blank=True,
        help_text='Не включая автора. Оставьте пустым, если лимит не задан.',
    )
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='open')
    moderation_status = models.CharField(
        'Статус модерации',
        max_length=15,
        choices=MODERATION_CHOICES,
        default='approved',
    )
    rejection_reason = models.TextField('Причина отклонения', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']

    def accepted_count(self):
        return self.applications.filter(status='accepted').count()

    def free_spots(self):
        if self.max_members is None:
            return None
        return max(self.max_members - self.accepted_count(), 0)

    def sync_recruitment_status(self):
        if self.max_members is not None:
            accepted = self.accepted_count()
            new_status = 'closed' if accepted >= self.max_members else 'open'
            if self.status != new_status:
                self.status = new_status
                self.save(update_fields=['status'])

    def __str__(self):
        return self.title


class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('accepted', 'Принята'),
        ('rejected', 'Отклонена'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    message = models.TextField('Сообщение', blank=True)
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField('Подана', auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']
        unique_together = ('project', 'applicant')

    def __str__(self):
        return f'{self.applicant.username} → {self.project.title}'


class ChatMessage(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='Проект',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='Автор',
    )
    text = models.TextField('Сообщение', blank=True)
    attachment = models.FileField(
        'Вложение',
        upload_to='chat_attachments/%Y/%m/',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField('Отправлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        ordering = ['created_at']

    def filename(self):
        return os.path.basename(self.attachment.name) if self.attachment else ''

    def __str__(self):
        return f'{self.author.username} в {self.project.title} ({self.created_at:%d.%m.%Y %H:%M})'


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Получатель',
    )
    event_key = models.CharField('Ключ события', max_length=120, blank=True, db_index=True)
    message = models.TextField('Текст уведомления')
    link = models.CharField('Ссылка', max_length=255, blank=True)
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'Уведомление для {self.recipient.username}: {self.message[:40]}'


def create_notification(recipient=None, message='', link='', event_key='', recipient_id=None):
    target_id = recipient.id if recipient is not None else recipient_id
    if not target_id:
        return None
    if event_key:
        existing = Notification.objects.filter(
            recipient_id=target_id, event_key=event_key
        ).first()
        if existing:
            return existing
    return Notification.objects.create(
        recipient_id=target_id,
        message=message,
        link=link,
        event_key=event_key,
    )
