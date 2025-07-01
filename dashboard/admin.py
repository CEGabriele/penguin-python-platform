from django.contrib import admin

from .models import Student, Uploads, Teacher, Class

# Register your models here.
admin.site.register(Student)
admin.site.register(Uploads)
admin.site.register(Teacher)
admin.site.register(Class)