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
    
class Curriculum(models.Model):
    name = models.CharField(max_length = 100)

    def __str__(self):
        return self.name

class Class(models.Model):
    name = models.CharField(max_length = 100)
    day = models.CharField(max_length = 9)
    time = models.TimeField()
    code = models.CharField(unique = True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name = "classes")
    location = models.CharField(default = "Lexington")
    curriculum = models.ForeignKey(Curriculum, on_delete = models.CASCADE, null = True, blank = True)
    
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

class HomeworkTemplate(models.Model):
    name = models.CharField(max_length=100)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    description = models.TextField()
    class_week = models.IntegerField(default = 0)

class AssignedHomework (models.Model):
    template = models.ForeignKey(HomeworkTemplate, on_delete=models.CASCADE)
    for_class = models.ForeignKey(Class, on_delete = models.CASCADE, null = True)
    due_date = models.DateField()
class HomeworkQuestion (models.Model):
    template = models.ForeignKey(HomeworkTemplate, on_delete = models.CASCADE, related_name = 'questions', null = True)
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
    assigned_homework = models.ForeignKey(AssignedHomework, on_delete = models.CASCADE, null = True)
    
    answer_text = models.TextField(blank = True)
    selected_choice = models.ForeignKey(QuestionChoices, on_delete = models.SET_NULL, null = True)
    upload = models.ForeignKey("dashboard.Uploads", on_delete=models.SET_NULL, null=True, blank=True)

class Material(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete = models.CASCADE, related_name = "materials")
    title = models.CharField()
    description = models.TextField(blank = True)
    file = models.FileField(upload_to = 'curriculum_materials', null = True, blank = True)
    link = models.URLField(blank = True, null = True)
    class_week = models.IntegerField(default = 0)

class PostedMaterial(models.Model):
    material = models.ForeignKey(Material, on_delete = models.CASCADE)
    for_class = models.ForeignKey(Class, on_delete = models.CASCADE, related_name = "posted_materials")
