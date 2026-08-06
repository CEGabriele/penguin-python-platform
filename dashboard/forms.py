from django import forms
from .models import User, Student, Teacher, Class, Curriculum
from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget
from .widgets import TeacherSelect2Widget, StudentSelect2Widget
from django.utils.html import format_html

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

    def save(self , commit=True):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        username = f"{first_name.lower()}{last_name.lower()}"

        # Handle duplicate usernames by appending a number
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

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

    def save(self , commit=True):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        username = f"{first_name.lower()}{last_name.lower()}"

        # Handle duplicate usernames by appending a number
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

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
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=ModelSelect2MultipleWidget(
            search_fields=['user__username__icontains', 'user__first_name__icontains', 'user__last_name__icontains'],
        ),
        required = False,
        
    )

    class Meta:
        model = Class
        fields = ['name', 'day', 'time', 'teacher', 'location', 'curriculum']

        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            students = self.cleaned_data.get('students')
            if students:
                for student in students:
                    student.classes.add(instance)
        return instance
    
class ClassStudentUpdateForm(forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=ModelSelect2MultipleWidget(
            search_fields=['user__username__icontains', 'user__first_name__icontains', 'user__last_name__icontains'],
        ),
    )
    class Meta:
        model = Class
        fields = ['students']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['students'].initial = self.instance.students.all()

class StudentPasswordResetForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        label="Student",
        widget=StudentSelect2Widget
    )
    new_password = forms.CharField(widget=PasswordInputWithToggle, label="New Password")


class TeacherPasswordResetForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        label="Teacher",
        widget=TeacherSelect2Widget
    )
    new_password = forms.CharField(widget=PasswordInputWithToggle, label="New Password")
