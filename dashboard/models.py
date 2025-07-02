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

def generate_code():
    return uuid.uuid4().hex[:6].upper()

class Teacher (models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)

class Class(models.Model):
    name = models.CharField(max_length = 100)
    day = models.TextField(max_length = 9)
    time = models.TimeField()
    code = models.CharField(unique = True, default = generate_code())
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name = "classes")

class Student (models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    date_of_birth = models.DateField
    classes = models.ManyToManyField(Class, related_name = 'students', null = True)

    def latest_file(self, which_type, which_class):
        return self.user.uploads_set.order_by("-uploaded_at").filter(file_type = which_type, for_class = which_class).first()


class Assignment (models.Model):
    title = models.TextField()
    for_class = models.ForeignKey(Class, on_delete = models.CASCADE)
    due_date = models.DateField()
    description = models.TextField()
    #how do we want teachers to share more information: file or doc? Do they need to share more information or is description enough?

class Uploads (models.Model):
    person = models.ForeignKey(User, on_delete = models.SET_NULL, null = True)
    id = models.BigAutoField(primary_key=True)
    file = models.FileField(upload_to="student_files")
    uploaded_at = models.DateTimeField(auto_now_add = True)
    for_class = models.ForeignKey(Class, related_name = 'files', on_delete=models.SET_NULL, null = True)
    file_type = models.CharField(max_length = 2)
    for_assignment = models.ForeignKey(Assignment, on_delete = models.SET_NULL, null = True)



