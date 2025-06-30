from django.contrib import admin

from .models import Student, StudentFile, Teacher, Class

# Register your models here.
admin.site.register(Student)
admin.site.register(StudentFile)
admin.site.register(Teacher)
admin.site.register(Class)