from django.urls import path
from .views import upload_student_file, student_file_view

urlpatterns = [
    path('upload/', upload_student_file, name='upload_file'),
    path('my-files/', student_file_view, name='student_files')
]