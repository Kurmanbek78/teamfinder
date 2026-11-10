import os
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import COURSE_CHOICES, StudyGroup, Profile, Project, Application, Skill, ChatMessage


ALLOWED_CHAT_EXTENSIONS = {
    'pdf', 'docx', 'xlsx', 'csv', 'txt',
    'png', 'jpg', 'webp',
    'py', 'js', 'ts', 'html', 'css', 'json', 'md',
}
MAX_CHAT_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 МБ


def get_grouped_skill_choices():
    groups = {}
    for skill in Skill.objects.select_related('direction').all():
        dir_name = skill.direction.name if skill.direction else 'Прочее'
        groups.setdefault(dir_name, []).append((skill.pk, skill.name))
    return list(groups.items())


class RegisterForm(UserCreationForm):
    course = forms.TypedChoiceField(
        label='Курс обучения',
        choices=[('', 'Выберите курс')] + list(COURSE_CHOICES),
        coerce=int,
        required=True,
    )
    study_group = forms.ModelChoiceField(
        label='Учебная группа',
        queryset=StudyGroup.objects.all(),
        required=True,
        empty_label='Выберите учебную группу',
    )

    class Meta:
        model = User
        fields = ('username', 'email')
        labels = {
            'username': 'Логин (имя пользователя)',
            'email': 'Электронная почта',
        }
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Например: ivanov_is31'}),
            'email': forms.EmailInput(attrs={'placeholder': 'student@college.edu'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['study_group'].queryset = StudyGroup.objects.order_by('course', 'name')
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Повторите пароль'
        if not StudyGroup.objects.exists():
            self.fields['study_group'].required = False

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course')
        study_group = cleaned_data.get('study_group')
        if course and study_group and study_group.course != course:
            self.add_error(
                'study_group',
                f'Группа {study_group.name} относится к {study_group.get_course_display()}, а выбран {course} курс.',
            )
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            course = self.cleaned_data.get('course')
            study_group = self.cleaned_data.get('study_group')
            if study_group:
                course = study_group.course
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    'role': 'student',
                    'course': course,
                    'study_group': study_group,
                    'group_status': 'pending',
                },
            )
        return user


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            'title',
            'description',
            'required_directions',
            'required_skills',
            'max_members',
            'status',
        )
        labels = {
            'title': 'Название проекта',
            'description': 'Описание проекта и задач команды',
            'required_directions': 'Нужные направления подготовки',
            'required_skills': 'Нужные навыки (по направлениям)',
            'max_members': 'Количество мест для участников (без учёта автора)',
            'status': 'Статус набора в команду',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Например: Мобильное приложение расписания колледжа'}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Опишите цель проекта, кого вы ищете в команду и какие задачи предстоит решить...'}),
            'required_directions': forms.CheckboxSelectMultiple,
            'required_skills': forms.CheckboxSelectMultiple,
            'max_members': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Без ограничений'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['required_skills'].choices = get_grouped_skill_choices()


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ('message',)
        labels = {'message': 'Сопроводительное сообщение автору'}
        widgets = {
            'message': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Расскажите, какую роль в команде хотите занять и чем сможете помочь проекту...',
                }
            )
        }


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ('text', 'attachment')
        labels = {
            'text': 'Текст сообщения',
            'attachment': 'Прикрепить файл (до 10 МБ)',
        }
        widgets = {
            'text': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Напишите сообщение команде или прикрепите файл проекта...',
                }
            ),
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            ext = os.path.splitext(attachment.name)[1].lower().lstrip('.')
            if ext not in ALLOWED_CHAT_EXTENSIONS:
                raise forms.ValidationError(
                    'Недопустимый формат файла. Разрешены: PDF, DOCX, XLSX, CSV, TXT, PNG, JPG, WEBP, PY, JS, TS, HTML, CSS, JSON и MD.'
                )
            if attachment.size > MAX_CHAT_ATTACHMENT_SIZE:
                raise forms.ValidationError(
                    'Размер файла превышает допустимый лимит 10 МБ.'
                )
        return attachment

    def clean(self):
        cleaned_data = super().clean()
        text = (cleaned_data.get('text') or '').strip()
        attachment = cleaned_data.get('attachment')
        if not text and not attachment and 'attachment' not in self.errors:
            raise forms.ValidationError('Введите текст сообщения или прикрепите файл.')
        cleaned_data['text'] = text
        return cleaned_data
