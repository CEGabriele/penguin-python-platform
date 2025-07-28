from django import forms
from .models import Uploads, Assignment, Class, HomeworkForm, HomeworkQuestion, QuestionChoices, StudentQuestionResponse
from django.forms import modelformset_factory, inlineformset_factory

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
class HomeworkQuestionForm(forms.ModelForm):
    class Meta:
        model = HomeworkQuestion
        fields = ['prompt', 'question_type']

class StudentAnswerForm(forms.ModelForm):
    class Meta:
        model = StudentQuestionResponse
        fields = ['question', 'selected_choice', 'answer_text', 'upload']
        widgets = {'question' : forms.HiddenInput(), 
                   'answer_text': forms.TextInput(attrs={'placeholder': 'Type your answer...'}),
                   'upload': forms.FileInput(), 
                   'selected_choice':forms.RadioSelect()}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        question = self.initial.get('question')
        
        if question:
            self.instance.question = question 

        if question and question.question_type == 'multiple_choice':
            self.fields['selected_choice'].queryset = question.choices.all()
        else:
            self.fields['selected_choice'].queryset = QuestionChoices.objects.none()


HomeworkQuestionFormSet = modelformset_factory(
    HomeworkQuestion, 
    form = HomeworkQuestionForm, 
    extra = 0, can_delete = True
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