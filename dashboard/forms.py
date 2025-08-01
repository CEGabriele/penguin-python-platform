from django import forms
from .models import User, Uploads, Student, Teacher, Assignment, Class, HomeworkForm, HomeworkQuestion, QuestionChoices, StudentQuestionResponse
from django.forms import modelformset_factory, inlineformset_factory
from django_select2.forms import ModelSelect2MultipleWidget

class HomeworkUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file', 'for_class']
        widgets = {'for_class': forms.HiddenInput(),}
    def save(self, commit=True, user = None):
        instance = super().save(commit = False)
        instance.person = user
        instance.file_type = "HW"
        if commit:
            instance.save()
        return instance

class ClassworkUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file', 'for_class']
        widgets = {'for_class': forms.HiddenInput(),}
    def save(self, commit=True, user = None):
        instance = super().save(commit = False)
        instance.person = user
        instance.file_type = "CW"
        if commit:
            instance.save()
        return instance

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'for_class', 'due_date']
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        if teacher:
            self.fields['for_class'].queryset = Class.objects.filter(teacher = teacher)
        self.fields['for_class'].label_from_instance = lambda obj: obj.name

class AssignmentUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file']

class HomeworkFormForm(forms.ModelForm):
    class Meta:
        model = HomeworkForm
        fields = ['name', 'for_class', 'description', 'due_date']
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        if teacher:
            self.fields['for_class'].queryset = Class.objects.filter(teacher = teacher)
        self.fields['for_class'].label_from_instance = lambda obj: obj.name
class HomeworkQuestionForm(forms.ModelForm):
    class Meta:
        model = HomeworkQuestion
        fields = ['prompt', 'question_type', 'uses_ai']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['uses_ai'].label = "Enable student AI review"

class StudentAnswerForm(forms.ModelForm):
    upload = forms.FileField(required=False, widget=forms.ClearableFileInput())
    
    class Meta:
        model = StudentQuestionResponse
        fields = ['question', 'selected_choice', 'answer_text']
        widgets = {'question' : forms.HiddenInput(), 
                   'answer_text': forms.TextInput(attrs={'placeholder': 'Type your answer...'}),
                   'selected_choice':forms.RadioSelect()}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        question = self.initial.get('question')
        
        if question:
            self.instance.question = question 

        if question and question.question_type == 'multiple_choice':
            self.fields['selected_choice'].queryset = question.choices.all()
            self.fields['selected_choice'].required = True
        else:
            self.fields['selected_choice'].queryset = QuestionChoices.objects.none()
            self.fields['selected_choice'].required = False

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

class ClassCreationForm(forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=ModelSelect2MultipleWidget(
            search_fields=['user__username__icontains', 'user__first_name__icontains', 'user__last_name__icontains'],
        ),
    )

    class Meta:
        model = Class
        fields = ['name', 'day', 'time', 'teacher', 'location']

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

HomeworkQuestionFormSet = modelformset_factory(
    HomeworkQuestion, 
    form = HomeworkQuestionForm, 
    extra = 0
)
HomeworkChoiceFormSet = inlineformset_factory(
    HomeworkQuestion, 
    QuestionChoices, 
    fields = ['text'], 
    extra = 2, 
    can_delete = True
)

StudentAnswerFormSet = modelformset_factory(
    StudentQuestionResponse,
    form = StudentAnswerForm
)