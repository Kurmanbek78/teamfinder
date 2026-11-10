import re
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .forms import RegisterForm, ProjectForm, ApplicationForm, ChatMessageForm
from .models import (
    Direction,
    Project,
    Application,
    Skill,
    StudyGroup,
    ChatMessage,
    Notification,
    create_notification,
)


def notifications_context(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
        }
    return {'unread_notifications_count': 0}


def notify_teachers_about_project(project):
    teachers = User.objects.filter(profile__role='teacher').exclude(id=project.owner_id)
    link = reverse('project_detail', args=[project.pk])
    for teacher in teachers:
        create_notification(
            recipient=teacher,
            message=f'Новый проект на проверку: «{project.title}» от {project.owner.username}.',
            link=link,
            event_key=f'project_pending:{project.pk}',
        )


def is_author(user):
    return hasattr(user, 'profile') and user.profile.role in ('student', 'author')


def is_teacher(user):
    return hasattr(user, 'profile') and user.profile.role == 'teacher'


def is_admin_role(user):
    return user.is_staff or user.is_superuser or (
        hasattr(user, 'profile') and user.profile.role == 'admin'
    )


def get_user_course(user):
    if not hasattr(user, 'profile'):
        return None
    if user.profile.course:
        return user.profile.course
    if user.profile.study_group_id and user.profile.study_group:
        return user.profile.study_group.course
    return None


def has_chat_access(project, user):
    if not user.is_authenticated:
        return False
    if project.owner_id == user.id:
        return True
    return Application.objects.filter(
        project=project, applicant=user, status='accepted'
    ).exists()


def home(request):
    projects = Project.objects.filter(
        status='open', moderation_status='approved'
    ).select_related('owner', 'owner__profile', 'owner__profile__study_group').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    direction = request.GET.get('direction', '').strip()
    skill = request.GET.get('skill', '').strip()
    sort = request.GET.get('sort', 'new').strip()
    if q:
        pattern = re.escape(q)
        projects = projects.filter(
            Q(title__iregex=pattern) | Q(description__iregex=pattern)
        )
    if direction:
        if direction.isdigit():
            dir_id = int(direction)
            projects = projects.filter(
                Q(required_directions__id=dir_id)
                | Q(required_skills__direction_id=dir_id)
            )
        else:
            dir_regex = f'^{re.escape(direction)}$'
            projects = projects.filter(
                Q(required_directions__name__iregex=dir_regex)
                | Q(required_skills__direction__name__iregex=dir_regex)
            )
    if skill:
        if skill.isdigit():
            projects = projects.filter(required_skills__id=int(skill))
        else:
            projects = projects.filter(
                required_skills__name__iregex=f'^{re.escape(skill)}$'
            )
    projects = list(
        projects.distinct().prefetch_related(
            'required_directions', 'required_skills__direction'
        )
    )
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_skill_ids = set(request.user.profile.skills.values_list('id', flat=True))
        for project in projects:
            req_ids = {s.id for s in project.required_skills.all()}
            if req_ids:
                project.matched_skills_count = len(req_ids & user_skill_ids)
                project.total_skills_count = len(req_ids)
        if sort == 'match':
            projects.sort(
                key=lambda p: (getattr(p, 'matched_skills_count', 0), p.created_at),
                reverse=True,
            )
    return render(request, 'home.html', {
        'projects': projects,
        'directions': Direction.objects.all(),
        'skills': Skill.objects.select_related('direction').all(),
        'q': q,
        'selected_direction': direction,
        'selected_skill': skill,
        'sort': sort,
    })


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()
    return render(
        request,
        'registration/register.html',
        {'form': form, 'study_groups': StudyGroup.objects.order_by('course', 'name')},
    )


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    can_moderate = request.user.is_authenticated and (
        is_teacher(request.user) or is_admin_role(request.user)
    )
    if (
        project.moderation_status != 'approved'
        and request.user != project.owner
        and not can_moderate
    ):
        raise PermissionDenied

    owner_course = get_user_course(project.owner)
    user_course = get_user_course(request.user) if request.user.is_authenticated else None
    same_course = (owner_course == user_course)

    context = {
        'project': project,
        'can_moderate': can_moderate,
        'can_access_chat': has_chat_access(project, request.user),
        'same_course': same_course,
        'owner_course': owner_course,
    }
    if request.user.is_authenticated:
        if request.user == project.owner or can_moderate:
            context['applications'] = project.applications.select_related(
                'applicant', 'applicant__profile', 'applicant__profile__study_group'
            ).prefetch_related(
                'applicant__profile__directions', 'applicant__profile__skills__direction'
            )
        if request.user != project.owner and not is_teacher(request.user):
            already = Application.objects.filter(
                project=project, applicant=request.user
            ).exists()
            context['already_applied'] = already
            if (
                not already
                and project.status == 'open'
                and project.moderation_status == 'approved'
                and same_course
            ):
                context['form'] = ApplicationForm()
    return render(request, 'project_detail.html', context)


@login_required
def my_projects(request):
    projects = Project.objects.filter(owner=request.user)
    return render(request, 'my_projects.html', {'projects': projects})


@login_required
def project_create(request):
    if not is_author(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.moderation_status = 'pending'
            project.rejection_reason = ''
            project.save()
            form.save_m2m()
            project.sync_recruitment_status()
            notify_teachers_about_project(project)
            messages.success(request, 'Проект создан и отправлен на проверку преподавателю')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'project_form.html', {'form': form, 'title': 'Новый проект'})


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.owner != request.user:
        raise PermissionDenied
    was_rejected = project.moderation_status == 'rejected'
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            updated = form.save(commit=False)
            if was_rejected:
                updated.moderation_status = 'pending'
                updated.rejection_reason = ''
            updated.save()
            form.save_m2m()
            updated.sync_recruitment_status()
            if was_rejected:
                notify_teachers_about_project(updated)
            messages.success(request, 'Проект обновлён')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'project_form.html', {'form': form, 'title': 'Редактирование проекта'})


@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.owner != request.user:
        raise PermissionDenied
    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Проект удалён')
        return redirect('my_projects')
    return render(request, 'project_confirm_delete.html', {'project': project})


@login_required
def project_apply(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if (
        project.owner == request.user
        or project.status != 'open'
        or project.moderation_status != 'approved'
        or is_teacher(request.user)
    ):
        raise PermissionDenied
    if get_user_course(project.owner) != get_user_course(request.user):
        messages.error(request, 'Подать заявку могут только студенты того же курса, что и автор проекта')
        return redirect('project_detail', pk=project.pk)
    if project.max_members is not None and project.accepted_count() >= project.max_members:
        project.sync_recruitment_status()
        messages.error(request, 'Все места в проекте уже заняты')
        return redirect('project_detail', pk=project.pk)
    if request.method == 'POST':
        if Application.objects.filter(project=project, applicant=request.user).exists():
            messages.error(request, 'Вы уже подавали заявку на этот проект')
        else:
            form = ApplicationForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.project = project
                application.applicant = request.user
                application.save()
                create_notification(
                    recipient=project.owner,
                    message=f'Новая заявка на проект «{project.title}» от {request.user.username}.',
                    link=reverse('project_detail', args=[project.pk]),
                    event_key=f'app_new:{application.pk}',
                )
                messages.success(request, 'Заявка отправлена')
    return redirect('project_detail', pk=project.pk)


@login_required
def application_decide(request, pk, action):
    application = get_object_or_404(Application, pk=pk)
    project = application.project
    if project.owner != request.user:
        raise PermissionDenied
    if request.method == 'POST' and action in ('accept', 'reject', 'remove'):
        old_status = application.status
        proj_link = reverse('project_detail', args=[project.pk])
        if action == 'accept':
            if (
                project.max_members is not None
                and application.status != 'accepted'
                and project.accepted_count() >= project.max_members
            ):
                messages.error(request, 'Все места в команде уже заполнены')
                return redirect('project_detail', pk=project.pk)
            application.status = 'accepted'
            application.save(update_fields=['status'])
            project.sync_recruitment_status()
            if old_status != 'accepted':
                create_notification(
                    recipient=application.applicant,
                    message=f'Ваша заявка на проект «{project.title}» принята!',
                    link=proj_link,
                    event_key=f'app_status:{application.pk}:accepted',
                )
            messages.success(request, 'Участник принят в команду')
        elif action == 'remove':
            application.status = 'rejected'
            application.save(update_fields=['status'])
            project.sync_recruitment_status()
            if old_status != 'rejected':
                create_notification(
                    recipient=application.applicant,
                    message=f'Ваша заявка на проект «{project.title}» отклонена.',
                    link=proj_link,
                    event_key=f'app_status:{application.pk}:rejected',
                )
            messages.success(request, 'Участник удалён из команды, место освобождено')
        else:
            application.status = 'rejected'
            application.save(update_fields=['status'])
            project.sync_recruitment_status()
            if old_status != 'rejected':
                create_notification(
                    recipient=application.applicant,
                    message=f'Ваша заявка на проект «{project.title}» отклонена.',
                    link=proj_link,
                    event_key=f'app_status:{application.pk}:rejected',
                )
            messages.success(request, 'Решение сохранено')
    return redirect('project_detail', pk=project.pk)


@login_required
def my_applications(request):
    applications = Application.objects.filter(applicant=request.user).select_related('project')
    return render(request, 'my_applications.html', {'applications': applications})


@login_required
def moderation_list(request):
    if not (is_teacher(request.user) or is_admin_role(request.user)):
        raise PermissionDenied
    pending_projects = Project.objects.filter(moderation_status='pending').select_related(
        'owner', 'owner__profile', 'owner__profile__study_group'
    ).prefetch_related('required_directions', 'required_skills__direction')
    reviewed_projects = Project.objects.exclude(moderation_status='pending').select_related(
        'owner', 'owner__profile', 'owner__profile__study_group'
    )[:20]
    return render(
        request,
        'moderation_list.html',
        {
            'pending_projects': pending_projects,
            'reviewed_projects': reviewed_projects,
        },
    )


@login_required
def project_moderate(request, pk, action):
    if not (is_teacher(request.user) or is_admin_role(request.user)):
        raise PermissionDenied
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        old_mod = project.moderation_status
        old_reason = project.rejection_reason
        proj_link = reverse('project_detail', args=[project.pk])
        if action == 'approve':
            project.moderation_status = 'approved'
            project.rejection_reason = ''
            project.save(update_fields=['moderation_status', 'rejection_reason'])
            if old_mod != 'approved':
                create_notification(
                    recipient=project.owner,
                    message=f'Ваш проект «{project.title}» одобрен преподавателем и опубликован в каталоге.',
                    link=proj_link,
                    event_key=f'proj_mod:{project.pk}:approved',
                )
            messages.success(request, 'Проект одобрен и опубликован в каталоге')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            if not reason:
                messages.error(request, 'Укажите причину отклонения проекта')
                return redirect('project_detail', pk=project.pk)
            project.moderation_status = 'rejected'
            project.rejection_reason = reason
            project.save(update_fields=['moderation_status', 'rejection_reason'])
            if old_mod != 'rejected' or old_reason != reason:
                create_notification(
                    recipient=project.owner,
                    message=f'Ваш проект «{project.title}» отклонён. Причина: {reason}',
                    link=proj_link,
                    event_key=f'proj_mod:{project.pk}:rejected:{reason}',
                )
            messages.success(request, 'Проект отклонён с комментарием для автора')
    return redirect('project_detail', pk=project.pk)


@login_required
def project_chat(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not has_chat_access(project, request.user):
        raise PermissionDenied
    if request.method == 'POST':
        form = ChatMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.project = project
            msg.author = request.user
            msg.save()
            recipient_ids = set(
                Application.objects.filter(project=project, status='accepted')
                .exclude(applicant=request.user)
                .values_list('applicant_id', flat=True)
            )
            if project.owner_id != request.user.id:
                recipient_ids.add(project.owner_id)
            chat_link = reverse('project_chat', args=[project.pk])
            for uid in recipient_ids:
                create_notification(
                    recipient_id=uid,
                    message=f'Новое сообщение от {request.user.username} в командном чате проекта «{project.title}».',
                    link=chat_link,
                    event_key=f'chat_msg:{msg.pk}:{uid}',
                )
            messages.success(request, 'Сообщение отправлено')
            return redirect('project_chat', pk=project.pk)
    else:
        form = ChatMessageForm()
    chat_messages = project.chat_messages.select_related('author', 'author__profile').all()
    team_members = project.applications.filter(status='accepted').select_related(
        'applicant', 'applicant__profile', 'applicant__profile__study_group'
    )
    return render(
        request,
        'project_chat.html',
        {
            'project': project,
            'chat_messages': chat_messages,
            'team_members': team_members,
            'form': form,
        },
    )


@login_required
def chat_attachment_download(request, pk):
    msg = get_object_or_404(ChatMessage.objects.select_related('project'), pk=pk)
    if not has_chat_access(msg.project, request.user):
        raise PermissionDenied
    if not msg.attachment:
        raise Http404
    return FileResponse(
        msg.attachment.open('rb'),
        as_attachment=True,
        filename=msg.filename(),
    )


@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    return render(
        request,
        'notifications.html',
        {'notifications': notifications},
    )


@login_required
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if request.method == 'POST' and not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect('notifications_list')


@login_required
def notifications_mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        messages.success(request, 'Все уведомления отмечены прочитанными')
    return redirect('notifications_list')
