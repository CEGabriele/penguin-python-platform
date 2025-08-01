from django.db import models
from django.contrib.auth.models import User
import uuid

"""
class Parent (models.Model):
    name = models.CharField(max_length = 100)
    email = models.EmailField()
    phone = models.CharField(max_length = 10)
    password = models.CharField()
"""



class Teacher (models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    is_admin = models.BooleanField(default = False)

    def __str__(self):
        return self.user.get_full_name()

class Class(models.Model):
    name = models.CharField(max_length = 100)
    day = models.CharField(max_length = 9)
    time = models.TimeField()
    code = models.CharField(unique = True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name = "classes")
    location = models.CharField(default = "Lexington")
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    def generate_code(self):
        return uuid.uuid4().hex[:6].upper()

class Student (models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    date_of_birth = models.DateField
    classes = models.ManyToManyField(Class, related_name = 'students')

    def latest_file(self, which_type, which_class):
        return self.user.uploads_set.order_by("-uploaded_at").filter(file_type = which_type, for_class = which_class).first()

    def __str__(self):
        return self.user.get_full_name()

class Uploads (models.Model):
    person = models.ForeignKey(User, on_delete = models.SET_NULL, null = True)
    id = models.BigAutoField(primary_key=True)
    file = models.FileField(upload_to="student_files")
    uploaded_at = models.DateTimeField(auto_now_add = True)
    for_class = models.ForeignKey(Class, related_name = 'files', on_delete=models.SET_NULL, null = True)
    file_type = models.CharField(max_length = 2)

class HomeworkForm (models.Model):
    name = models.CharField(max_length = 100)
    #might change to many to many 
    for_class = models.ForeignKey(Class, on_delete = models.CASCADE, null = True)
    description = models.TextField()
    due_date = models.DateField()
class HomeworkQuestion (models.Model):
    form = models.ForeignKey(HomeworkForm, on_delete = models.CASCADE, related_name = 'questions')
    prompt = models.TextField()
    question_type = models.CharField(max_length = 20, choices = [('short', 'Short Answer'), ('file', 'File Upload'), ('multiple_choice', 'Multiple Choice')])
    uses_ai = models.BooleanField(default = False)
    extra_ai_instructions = models.TextField(blank = True)

class QuestionChoices (models.Model):
    question = models.ForeignKey(HomeworkQuestion, on_delete = models.CASCADE, related_name = 'choices')
    text = models.TextField()
    is_correct = models.BooleanField(default = False)
    def __str__(self):
        return self.text
    def setCorrect(self):
        self.is_correct = True
        self.save()

class StudentQuestionResponse (models.Model):
    student = models.ForeignKey(Student, on_delete = models.CASCADE, null = True)
    question = models.ForeignKey(HomeworkQuestion, on_delete=models.CASCADE)
    answer_text = models.TextField(blank = True)
    selected_choice = models.ForeignKey(QuestionChoices, on_delete = models.SET_NULL, null = True)
    upload = models.ForeignKey("dashboard.Uploads", on_delete=models.SET_NULL, null=True, blank=True)