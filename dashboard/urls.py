from django.urls import path
from .views import download_file_view, student_dashboard, teacher_dashboard, view_student, student_assignments, teacher_assignments_list, student_form_view, responses_view, student_class_view, teacher_class_view, get_code_feedback, admin_dashboard, admin_class_view, create_homework_template, assign_homework_assignment, get_due_date_form, post_material, create_material, download_material_view, editor_view


urlpatterns = [
    path('download/<int:file_id>/', download_file_view, name = 'download_file'),
    path('download-material/<int:file_id>/', download_material_view, name = 'download_material'),
    path('student-dashboard/', student_dashboard, name = 'student_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name = 'teacher_dashboard'),
    path('view-student/<str:username>/', view_student, name = 'view_student'),
    path('my-assignments', student_assignments, name = 'student_assignments'),
    path('assigned-assignments', teacher_assignments_list, name = 'teacher_assignments'),
    path('create-homework-template/', create_homework_template, name = "create_homework_template" ),
    path('student-form/<int:assigned_hw_id>', student_form_view, name = 'student_form_view'),
    path('form-results/<int:assigned_hw_id>/', responses_view, name = 'responses_view'),
    path('student-class-view/<str:class_code>/', student_class_view, name="student_class_view"),
    path('teacher-class-view/<str:class_code>/', teacher_class_view, name="teacher_class_view"),
    path("get-code-feedback/",get_code_feedback , name="get_code_feedback"),
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("admin-class-view/<str:class_id>/", admin_class_view, name="admin_class_view"),
    path('set-due-date/<int:class_id>/<int:template_id>/', get_due_date_form, name="get_homework_due_date_form"),
    path('assign_homework_assignment', assign_homework_assignment, name="assign_homework_assignment"),
    path('post_material/<int:class_id>/<int:material_id>/', post_material, name='post_material_htmx'),
    path('create_material', create_material, name='create_material'),
    path('editor/', editor_view, name='editor_view'),

]