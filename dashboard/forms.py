from django import forms
from .models import User, Student, Teacher, Class, Curriculum
from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget
from .widgets import TeacherSelect2Widget, StudentSelect2Widget

class StudentCreationForm(forms.Form):
    username = forms.CharField(max_length=150, label='Username')
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    def save(self , commit=True):
        user = User.objects.create_user(
            username = self.cleaned_data['username'],
            first_name = self.cleaned_data['first_name'],
            last_name = self.cleaned_data['last_name'],
            password = self.cleaned_data['password']
        )
        user.save()
        Student.objects.create(user=user)
        return user

class TeacherCreationForm(forms.Form):
    username = forms.CharField(max_length=150, label='Username')
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    email = forms.EmailField(max_length=254, label='Email')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    is_admin = forms.BooleanField(required=False, label='Is Admin')
    def save(self , commit=True):
        user = User.objects.create_user(
            username = self.cleaned_data['username'],
            first_name = self.cleaned_data['first_name'],
            last_name = self.cleaned_data['last_name'],
            email = self.cleaned_data['email'],
            password = self.cleaned_data['password'],
            
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
    new_password = forms.CharField(widget=forms.PasswordInput, label="New Password")


class TeacherPasswordResetForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        label="Teacher",
        widget=TeacherSelect2Widget
    )
    new_password = forms.CharField(widget=forms.PasswordInput, label="New Password")
