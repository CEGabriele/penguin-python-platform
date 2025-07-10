from django.urls import path
from .models import Student
from . import views
from .views import download_file_view, student_dashboard, teacher_dashboard, view_student, create_assignment, student_assignments, student_assignment_view, teacher_assignments_list, teacher_assignment_detail, create_homework_form, student_form_view, responses_view


urlpatterns = [
    path('download/<int:file_id>/', download_file_view, name = 'download_file'),
    path('student-dashboard/', student_dashboard, name = 'student_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name = 'teacher_dashboard'),
    path('create-assignment/',  create_assignment, name = 'create_assignment'),
    path('view-student/<str:username>/', view_student, name = 'view_student'),
    path('my-assignments', student_assignments, name = 'student_assignments'),
    path('assignment-details/<int:assignment_id>/', student_assignment_view, name = 'assignment_details'),
    path('assigned-assignments', teacher_assignments_list, name = 'teacher_assignments'),
    path('teacher-assignment-details/<int:assignment_id>/', teacher_assignment_detail, name = "teacher_assignment_details"),
    path('create-homework-form/', create_homework_form, name = "create_homework_form" ),
    path('student-form/<int:form_id>', student_form_view, name = 'student_form_view'),
    path('form-results/<int:form_id>/', responses_view, name = 'responses_view')

]