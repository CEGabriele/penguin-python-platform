from django import forms
from .models import User, Student, Teacher, Class, Curriculum, Assignment
from django.utils.html import format_html


def generate_unique_username(first_name, last_name):
    username = f"{first_name.lower()}{last_name.lower()}"
    base_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    return username


class PasswordInputWithToggle(forms.PasswordInput):
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        attrs['class'] = attrs.get('class', '') + ' password-input'
        password_input = super().render(name, value, attrs, renderer)
        toggle_icon = format_html(
            '<span class="password-toggle"><i class="bi bi-eye"></i></span>'
        )
        return format_html('<div class="password-field">{}{}</div>', password_input, toggle_icon)


class StudentCreationForm(forms.Form):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    password = forms.CharField(widget=PasswordInputWithToggle, label='Password')
    confirm_duplicate = forms.BooleanField(
        required=False,
        label='Yes, this is a different student. Create a second account',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.duplicate_matches = []

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        if not (first_name and last_name):
            return cleaned_data

        self.duplicate_matches = list(
            Student.objects
            .filter(user__first_name__iexact=first_name, user__last_name__iexact=last_name)
            .select_related('user')
            .prefetch_related('classes')
            .order_by('user__username')
        )

        if self.duplicate_matches and not cleaned_data.get('confirm_duplicate'):
            count = len(self.duplicate_matches)
            raise forms.ValidationError(
                f"{count} student account{'' if count == 1 else 's'} named "
                f"{first_name} {last_name} already exist{'s' if count == 1 else ''}. "
                "If this is the same student, add the existing account to the class "
                "instead of creating a new one."
            )

        return cleaned_data

    def save(self , commit=True):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        username = generate_unique_username(first_name, last_name)

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=self.cleaned_data['password']
        )
        user.save()
        Student.objects.create(user=user)
        return user

class TeacherCreationForm(forms.Form):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    email = forms.EmailField(max_length=254, label='Email')
    password = forms.CharField(widget=PasswordInputWithToggle, label='Password')
    is_admin = forms.BooleanField(required=False, label='Is Admin')
    confirm_duplicate = forms.BooleanField(
        required=False,
        label='Yes, this is a different teacher. Create a second account',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_matches = []

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        if not (first_name and last_name):
            return cleaned_data

        self.duplicate_matches = list(
            Teacher.objects
            .filter(user__first_name__iexact=first_name, user__last_name__iexact=last_name)
            .select_related('user')
            .prefetch_related('classes')
            .order_by('user__username')
        )

        if self.duplicate_matches and not cleaned_data.get('confirm_duplicate'):
            count = len(self.duplicate_matches)
            raise forms.ValidationError(
                f"{count} teacher account{'' if count == 1 else 's'} named "
                f"{first_name} {last_name} already exist{'s' if count == 1 else ''}. "
                "If this is the same teacher, use the existing account instead of "
                "creating a new one."
            )

        return cleaned_data

    def save(self , commit=True):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        username = generate_unique_username(first_name, last_name)

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
        )
        user.save()
        Teacher.objects.create(user=user, is_admin=self.cleaned_data.get('is_admin', False))
        return user

class CurriculumCreationForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = ['name']
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance

class ClassCreationForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'day', 'time', 'teacher', 'location', 'curriculum']

        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['time'].required = False
        self.fields['curriculum'].required = False

class ClassEditForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'day', 'time', 'location', 'curriculum']
        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['time'].required = False
        self.fields['curriculum'].required = False

class StudentPasswordResetForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all().select_related('user').order_by('user__first_name', 'user__last_name'),
        label="Student",
    )
    new_password = forms.CharField(widget=PasswordInputWithToggle, label="New Password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].label_from_instance = lambda obj: f"{obj.user.get_full_name()} ({obj.user.username})"


class TeacherPasswordResetForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all().select_related('user').order_by('user__first_name', 'user__last_name'),
        label="Teacher",
    )
    new_password = forms.CharField(widget=PasswordInputWithToggle, label="New Password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].label_from_instance = lambda obj: f"{obj.user.get_full_name()} ({obj.user.username})"

class AssignmentEditForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'curriculum']
        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
