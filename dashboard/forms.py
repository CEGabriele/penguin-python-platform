from django import forms
from .models import Uploads, Assignment, Class

class HomeworkUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file', 'for_class']
        widgets = {'for_class': forms.HiddenInput(),}
    def save(self, commit=True, user = None):
        instance = super().save(commit = False)
        instance.person = user
        instance.type = "HW"
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
        instance.type = "CW"
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