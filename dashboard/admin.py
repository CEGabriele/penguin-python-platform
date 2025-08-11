from django.contrib import admin

from .models import Student, Uploads, Teacher, Class, HomeworkTemplate, AssignedHomework, HomeworkQuestion, QuestionChoices, StudentQuestionResponse

# Register your models here.
admin.site.register(Student)
admin.site.register(Uploads)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(HomeworkQuestion)
admin.site.register(AssignedHomework)
admin.site.register(HomeworkTemplate)
admin.site.register(QuestionChoices)
admin.site.register(StudentQuestionResponse)