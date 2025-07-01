from django.urls import path
from .views import download_file_view, student_dashboard, teacher_dashboard


urlpatterns = [
    #path('upload/', upload_student_file, name='upload_file'),
    #path('my-files/', student_file_view, name='student_files'),
    path('download/<int:file_id>/', download_file_view, name = 'download_file'),
    path('student-dashboard/', student_dashboard, name = 'student_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name = 'teacher_dashboard')
]