from django.urls import path
from .views import *


urlpatterns = [
    path('student-dashboard/', student_dashboard, name = 'student_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name = 'teacher_dashboard'),
    path('view-student/<str:username>/', view_student, name = 'view_student'),
    path('student-class-view/<str:class_code>/', student_class_view, name="student_class_view"),
    path('teacher-class-view/<str:class_code>/', teacher_class_view, name="teacher_class_view"),
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("admin-class-view/<str:class_id>/", admin_class_view, name="admin_class_view"),
    path('editor/',editor_view, name='editor_view'),
    path('create-assignment/',create_assignment, name='create_assignment'),
    path("assignment/<int:assigned_id>/submissions/", teacher_view_submissions, name="teacher_view_submissions"),
    path("teacher-assignment/<int:assignment_id>/", teacher_assignment_detail, name="teacher_assignment_detail"),
    path('assign_assignment_to_class/<int:assignment_id>/', assign_assignment_to_class, name='assign_assignment_to_class'),
    path("assignment/<int:assigned_id>/submit/",submit_assignment,name="submit_assignment"),
    path("editor/projects/", editor_projects),
    path("editor/create-project/", create_editor_project),
    path("editor/project/<int:project_id>/file/<path:file_path>/",editor_project_file),
    path("editor/project/<int:project_id>/create-file/",create_project_file),
    path("editor/project/<int:project_id>/files/", get_project_files),
    path("editor/project/<int:project_id>/teacher-files/", get_project_files_for_teacher, name="teacher_project_files"),
    path("editor/project/<int:project_id>/rename-file/", rename_file),
    path("editor/project/<int:project_id>/delete-file/", delete_file),
    path("editor/move-file/", move_file, name="move_file"),
]