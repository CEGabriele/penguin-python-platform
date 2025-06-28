from django import forms
from .models import StudentFile

class StudentFileForm(forms.ModelForm):
    class Meta:
        model = StudentFile
        fields = ['file']