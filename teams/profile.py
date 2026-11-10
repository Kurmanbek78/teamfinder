from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import get_grouped_skill_choices
from .models import COURSE_CHOICES, StudyGroup, Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('course', 'study_group', 'bio', 'directions', 'skills')
        labels = {
            'course': 'Курс обучения',
            'study_group': 'Учебная группа',
            'bio': 'О себе и своём опыте',
            'directions': 'Мои направления',
            'skills': 'Мои навыки (по направлениям)',
        }
        widgets = {
            'bio': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Расскажите о своих учебных интересах, технологиях и роли, в которой хотите развиваться...',
                }
            ),
            'directions': forms.CheckboxSelectMultiple,
            'skills': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['skills'].choices = get_grouped_skill_choices()
        if 'course' in self.fields:
            self.fields['course'].choices = [('', 'Выберите курс')] + list(COURSE_CHOICES)
        if 'study_group' in self.fields:
            self.fields['study_group'].queryset = StudyGroup.objects.order_by('course', 'name')
            self.fields['study_group'].empty_label = 'Выберите учебную группу'
        if self.instance and self.instance.role != 'student':
            self.fields.pop('course', None)
            self.fields.pop('study_group', None)

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


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    old_group_id = profile.study_group_id
    old_course = profile.course
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            updated = form.save(commit=False)
            if (
                updated.role == 'student'
                and (updated.study_group_id != old_group_id or updated.course != old_course)
            ):
                updated.group_status = 'pending'
            updated.save()
            form.save_m2m()
            messages.success(request, 'Профиль сохранён')
            return redirect('profile_edit')
    else:
        form = ProfileForm(instance=profile)
    return render(
        request,
        'project_form.html',
        {'form': form, 'title': 'Мой профиль', 'profile_obj': profile},
    )
