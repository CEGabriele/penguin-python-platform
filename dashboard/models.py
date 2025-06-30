from django.db import models
from django.contrib.auth.models import User
import uuid

# Create your models here.

"""
class Parent (models.Model):
    name = models.CharField(max_length = 100)
    email = models.EmailField()
    phone = models.CharField(max_length = 10)
    password = models.CharField()

class Teacher (models.Model):
    name = models.CharField(max_length = 100)
    email = models.EmailField()
    password = models.CharField()

class Class(models.Model):
    name = models.CharField(max_length = 100)
    day = models.TextField()
    time = models.IntegerField()
    semester = models.TextField()
    teacher = models.ForeignKey(Teacher, on_delete = models.SET_NULL, null = True)

"""

class Student (models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    date_of_birth = models.DateField

class StudentFile (models.Model):
    student = models.ForeignKey(Student, on_delete = models.SET_NULL, null = True)
    id = models.BigAutoField(primary_key=True)
    file = models.FileField(upload_to="student_files")
    uploaded_at = models.DateTimeField(auto_now_add = True)