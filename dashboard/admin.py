from django.contrib import admin
from django import forms
import csv
from django.http import HttpResponse

from .models import Student, Teacher, Class, Curriculum, CodeProject, ProjectFile, Assignment, AssignedToClass

def export_student_passwords(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_passwords.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Username', 'Password'])
    for student in queryset:
        writer.writerow([
            student.user.get_full_name(),
            student.user.username,
            student.password_text or ''
        ])
    return response

export_student_passwords.short_description = "Export passwords to CSV"

class StudentAdminForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Leave blank to keep the current password. Enter a new password to update both the login password and the stored plaintext password."
    )

    class Meta:
        model = Student
        fields = ['date_of_birth', 'classes', 'password_text']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['password'].label = f"Change password for {self.instance.user.get_full_name()}"

    def save(self, commit=True):
        student = super().save(commit=False)
        password = self.cleaned_data.get('password')

        if password:
            student.user.set_password(password)
            student.password_text = password
            if commit:
                student.user.save()

        if commit:
            student.save()
        return student

class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('get_full_name', 'get_username', 'password_text', 'date_of_birth')
    list_filter = ('classes',)
    search_fields = ('user__first_name', 'user__last_name', 'user__username')
    actions = [export_student_passwords]
    fieldsets = (
        (None, {
            'fields': ('date_of_birth', 'classes', 'password_text', 'password')
        }),
    )

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'

# Register your models here.
admin.site.register(Student, StudentAdmin)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(Curriculum)
admin.site.register(CodeProject)
admin.site.register(ProjectFile)
admin.site.register(Assignment)
admin.site.register(AssignedToClass)