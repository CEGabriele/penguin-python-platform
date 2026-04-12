from django.contrib import admin

from .models import Student, Teacher, Class, Curriculum, CodeProject, ProjectFile, Assignment, AssignedToClass

# Register your models here.
admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(Curriculum)
admin.site.register(CodeProject)
admin.site.register(ProjectFile)
admin.site.register(Assignment)
admin.site.register(AssignedToClass)