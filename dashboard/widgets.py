from .models import Teacher, Student
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from django.urls import reverse

class TeacherSelect2Widget(ModelSelect2Widget):
    model = Teacher
    search_fields = [
        "user__username__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
    ]

    def get_queryset(self):
        return Teacher.objects.select_related("user").all()

class StudentSelect2Widget(ModelSelect2Widget):
    model = Student
    search_fields = [
        "user__username__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
    ]

    def get_queryset(self):
        return Student.objects.select_related("user").all()


class StudentSelect2MultipleWidget(ModelSelect2MultipleWidget):
    model = Student
    search_fields = [
        "user__username__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
    ]

    def get_queryset(self):
        return Student.objects.select_related("user").all()