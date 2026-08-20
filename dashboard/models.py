from django.db import models
from django.contrib.auth.models import User
import uuid, os
from .storages import MediaRootS3Boto3Storage
from django.utils.text import slugify

# Referenced by dotted path in migrations 0003/0006 (Uploads.file upload_to).
# Keep even though Uploads is gone, or `migrate` on a fresh DB breaks replaying that history.
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
        ('All Week', 'All Week'),
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
    time = models.TimeField(blank=True, null=True)
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
    date_of_birth = models.DateField(null=True, blank=True)
    classes = models.ManyToManyField(Class, related_name = 'students')
    password_text = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.get_full_name()

def get_user_role(user):
    if hasattr(user, "student"):
        return "student"
    if hasattr(user, "teacher"):
        return "teacher"
    return "user"

# Referenced by dotted path in migrations 0003-0007/0015 (Uploads.file upload_to).
# Keep even though Uploads is gone, or `migrate` on a fresh DB breaks replaying that history.
def upload_path(instance, filename):
    user = instance.person

    if not user or not hasattr(user, "student"):
        return f"uploads/unknown/{filename}"

    student = user.student

    if not instance.for_class:
        return f"student_files/student_{student.id}/drafts/{filename}"

    base = (
        f"student_files/"
        f"student_{student.id}/"
        f"class_{instance.for_class.id}"
    )

    # Naming homework after assignment title if applicable
    if instance.assignment:
        assignment_name = slugify(instance.assignment.title) or "assignment"
        return f"{base}/assignments/{assignment_name}.py"

    safe = filename or "classwork.py"
    return f"{base}/classwork/{safe}"


class Assignment(models.Model):
    created_by = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    def __str__(self) -> str:
        return self.title
    
class AssignedToClass(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="assigned_instances"
    )
    for_class = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="assigned_assignments"
    )
    due_date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "for_class"],
                name="unique_assignment_per_class"
            )
        ]

    def __str__(self) -> str:
        return f"{self.assignment.title} assigned to {self.for_class.name}"

class CodeProject(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="code_projects")
    for_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null = True)
    assignment = models.ForeignKey(
        "Assignment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="projects",
    )

    created_at = models.DateTimeField(auto_now_add = True)
    last_edited = models.DateTimeField(auto_now = True)

    name = models.CharField(max_length = 200, blank = True, null = True)

    is_template = models.BooleanField(default=False)

    submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "for_class", "assignment"],
                name="unique_user_class_assignment_project"
            )
        ]
    def __str__(self):
        return f"{self.name} ({self.owner})"


def project_file_path(instance, filename):
    project = instance.project
    return f"projects/user_{project.owner.id}/project_{project.id}/{instance.path}"
    
class ProjectFile(models.Model):
    project = models.ForeignKey(CodeProject, related_name="files", on_delete=models.CASCADE)
    path = models.CharField(max_length=300)
    file = models.FileField(storage = MediaRootS3Boto3Storage(), upload_to=project_file_path)
    last_edited = models.DateTimeField(auto_now = True)

    class Meta:
        constraints = [
            models.UniqueConstraint (
                fields = ["project", "path"],
                name = "unique_file_path_per_project"
            )
        ]

    def __str__(self):
        return f"{self.project.name} - {self.path}"


class ProjectFeedback(models.Model):
    project = models.OneToOneField(CodeProject, on_delete=models.CASCADE, related_name="feedback")
    grader = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="given_feedback")
    comment = models.TextField(blank=True)
    read_by_student = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback for {self.project.name}"


class CodeLineComment(models.Model):
    project = models.ForeignKey(CodeProject, on_delete=models.CASCADE, related_name="line_comments")
    file_path = models.CharField(max_length=300)
    line_number = models.IntegerField()
    end_line = models.IntegerField(null=True, blank=True)
    comment = models.TextField()
    grader = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="line_comments_given")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "file_path", "line_number"],
                name="unique_line_comment_per_project_file_line"
            )
        ]

    def __str__(self):
        if self.end_line and self.end_line != self.line_number:
            return f"Comment on {self.project.name}:{self.file_path}:{self.line_number}-{self.end_line}"
        return f"Comment on {self.project.name}:{self.file_path}:{self.line_number}"