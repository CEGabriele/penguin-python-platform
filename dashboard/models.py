from django.db import models
from django.contrib.auth.models import User
import uuid, os
from .storages import MediaRootS3Boto3Storage

def unique_student_upload_path(instance, filename):
    return f"student_uploads/{filename}"

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
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    LOCATION_CHOICES = [

        ('Lexington', 'Lexington'),
        ('Acton', 'Acton'),
        ('Newton', 'Newton'),
        ('Brookline', 'Brookline'),
        ('Cobble Hill', 'Cobble Hill'),
        ('Park Slope', 'Park Slope'),
        ('Online', 'Online'),
    ]
            
    name = models.CharField(max_length = 100)
    day = models.CharField(choices=DAY_CHOICES)
    time = models.TimeField()
    code = models.CharField(unique = True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name = "classes")
    location = models.CharField(choices=LOCATION_CHOICES)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, blank = True, null = True, related_name = "classes")
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
    file = models.FileField(storage=MediaRootS3Boto3Storage(), upload_to="student_files/")
    uploaded_at = models.DateTimeField(auto_now_add = True)
    for_class = models.ForeignKey(Class, related_name = 'files', on_delete=models.SET_NULL, null = True)
    file_type = models.CharField(max_length = 2, default = "hw")
    display_name = models.CharField(max_length = 200, blank = True, null = True)

class HomeworkTemplate(models.Model):
    name = models.CharField(max_length=100)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    description = models.TextField()
    class_week = models.IntegerField(default = 0)
    new_material = models.TextField(blank = True, null = True)

class AssignedHomework (models.Model):
    template = models.ForeignKey(HomeworkTemplate, on_delete=models.CASCADE)
    for_class = models.ForeignKey(Class, on_delete = models.CASCADE, null = True)
    due_date = models.DateField()
    
class HomeworkQuestion (models.Model):
    template = models.ForeignKey(HomeworkTemplate, on_delete = models.CASCADE, related_name = 'questions', null = True)
    prompt = models.TextField()
    question_type = models.CharField(max_length = 20, choices = [('short', 'Short Answer'), ('file', 'Code Editor'), ('multiple_choice', 'Multiple Choice')])
    uses_ai = models.BooleanField(default = False)

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


class CompletedCurriculum(models.Model):
    student = models.ForeignKey(Student, on_delete = models.CASCADE)
    curriculum = models.ForeignKey(Curriculum, on_delete = models.CASCADE)
    completed_weeks = models.IntegerField(default = 0)

class AIFeedback(models.Model):
    question = models.ForeignKey(HomeworkQuestion, on_delete=models.CASCADE, related_name='feedback')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True)
    response = models.TextField()

    def __str__(self):
        return f"Feedback for {self.student.user.get_full_name()} on question {self.question.prompt}"


class Assignment(models.Model):
    created_by = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200)
    description = models.TextField()

    def __str__(self) -> str:
        return self.title
    
class AssignedToClass(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='assigned_classes')
    for_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    due_date = models.DateField()

    def __str__(self) -> str:
        return f"{self.assignment.title} assigned to {self.for_class.name}"
    
class StudentSubmission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    upload = models.ForeignKey(
        Uploads,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_submissions",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted = models.BooleanField(default=False, blank = True)

    ai_feedback = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Submission by {self.student.user.get_full_name()} for {self.assignment.title}"