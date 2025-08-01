from django.contrib import admin

from .models import Student, Uploads, Teacher, Class, HomeworkForm, HomeworkQuestion, QuestionChoices, StudentQuestionResponse

# Register your models here.
admin.site.register(Student)
admin.site.register(Uploads)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(HomeworkForm)
admin.site.register(HomeworkQuestion)
admin.site.register(QuestionChoices)
admin.site.register(StudentQuestionResponse)