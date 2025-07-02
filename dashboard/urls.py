from django.urls import path
from .models import Student
from . import views
from .views import download_file_view, student_dashboard, teacher_dashboard, view_student


urlpatterns = [
    path('download/<int:file_id>/', download_file_view, name = 'download_file'),
    path('student-dashboard/', student_dashboard, name = 'student_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name = 'teacher_dashboard'),
    path('view-student/<str:username>/', view_student, name = 'view_student')
]