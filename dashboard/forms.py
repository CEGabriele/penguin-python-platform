from django import forms
from .models import Uploads

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