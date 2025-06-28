from django.contrib import admin

from .models import Student, StudentFile

# Register your models here.
admin.site.register(Student)
admin.site.register(StudentFile)