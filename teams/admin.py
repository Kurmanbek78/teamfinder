from django.contrib import admin
from django.urls import reverse
from .models import (
    StudyGroup,
    Direction,
    Skill,
    Profile,
    Project,
    Application,
    ChatMessage,
    Notification,
    create_notification,
)


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'curator')
    list_filter = ('course',)
    search_fields = ('name', 'curator__username')


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'direction')
    list_filter = ('direction',)
    search_fields = ('name',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'course', 'study_group', 'group_status')
    list_filter = ('role', 'course', 'group_status', 'study_group')
    list_editable = ('role', 'course', 'study_group', 'group_status')
    search_fields = ('user__username', 'user__email', 'study_group__name')
    actions = ['confirm_groups']

    @admin.action(description='Подтвердить учебную группу у выбранных профилей')
    def confirm_groups(self, request, queryset):
        to_confirm = list(
            queryset.exclude(group_status='confirmed').select_related('user', 'study_group')
        )
        queryset.update(group_status='confirmed')
        for profile in to_confirm:
            group_label = profile.study_group.name if profile.study_group else 'группа'
            create_notification(
                recipient=profile.user,
                message=f'Администратор подтвердил вашу учебную группу ({group_label}).',
                link=reverse('profile_edit'),
                event_key=f'group_confirmed:{profile.pk}:{profile.study_group_id}',
            )


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'moderation_status', 'max_members', 'created_at')
    list_filter = ('status', 'moderation_status')
    search_fields = ('title', 'owner__username')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('project', 'applicant', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('project__title', 'applicant__username')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('project', 'author', 'created_at')
    list_filter = ('project',)
    search_fields = ('project__title', 'author__username', 'text')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('recipient__username', 'message')
