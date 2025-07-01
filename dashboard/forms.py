from django import forms
from .models import Uploads

class HomeworkUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file']
    def save(self, commit=True, user = None):
        instance = super().save(commit = False)
        instance.user = user
        instance.type = "HW"
        if commit:
            instance.save()

class ClassworkUpload(forms.ModelForm):
    class Meta:
        model = Uploads
        fields = ['file']
    def save(self, commit=True, user = None):
        instance = super().save(commit = False)
        instance.user = user
        instance.type = "CW"
        if commit:
            instance.save()
