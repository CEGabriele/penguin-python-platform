from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from .forms import StudentCreationForm, TeacherCreationForm, CurriculumCreationForm, ClassCreationForm, ClassStudentUpdateForm, StudentPasswordResetForm, TeacherPasswordResetForm
from .models import *
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import OuterRef, Exists, Count, Q, Max
from collections import defaultdict
from django.db import connection
from django.utils import timezone
from django.core.files.base import ContentFile
from django.utils.encoding import force_str
from django.views.decorators.http import require_GET

def student_required(view_function):
    def wrapper(request, *args, **kwargs):
        if not Student.objects.filter(user = request.user).exists():
            return redirect('teacher_dashboard')
        return view_function(request, *args, **kwargs)
    return wrapper

def teacher_required(view_function):
    def wrapper(request, *args, **kwargs):
        if not Teacher.objects.filter(user = request.user).exists():
            return redirect('student_dashboard')

        return view_function(request, *args, **kwargs)
    return wrapper

@login_required
@student_required
def student_dashboard(request):
    student = Student.objects.get(user = request.user) 
    user = request.user
    
    classes = []

    for section in student.classes.all():
        class_projects = CodeProject.objects.filter(
            owner=user,
            for_class=section
        ).order_by("-last_edited")

        hw_projects = class_projects.filter(assignment__isnull=False)
        cw_projects = class_projects.filter(assignment__isnull=True)

        assigned_assignments = (
            AssignedToClass.objects
            .filter(for_class=section)
            .select_related("assignment")
            .order_by("due_date")
        )

        submitted_ids = set(
            CodeProject.objects.filter(
                owner=user,
                for_class=section,
                submitted=True,
                assignment__isnull=False
            ).values_list("assignment_id", flat=True)
        )

        upcoming_assignments = [
            assigned for assigned in assigned_assignments
            if assigned.assignment_id not in submitted_ids
        ]

        classes.append({
            'class': section,
            'hw_projects': hw_projects,
            'cw_projects': cw_projects,
            'upcoming_assignments': upcoming_assignments,
        })


    return render(request, 'student_dashboard.html', {
        'student': student,
        'classes': classes
    })

@login_required
@teacher_required
def teacher_dashboard(request):
    teacher = Teacher.objects.get(user = request.user)
    classes = teacher.classes.all()

    class_info = []

    for section in classes:
        student_info = []

        for student in section.students.all():

            latest_hw_project = (
                CodeProject.objects
                .filter(
                    owner=student.user,
                    for_class=section,
                    assignment__isnull=False
                )
                .order_by("-last_edited")
                .first()
            )

            latest_cw_project = (
                CodeProject.objects
                .filter(
                    owner=student.user,
                    for_class=section,
                    assignment__isnull=True
                )
                .order_by("-last_edited")
                .first()
            )

            student_info.append({
                'student': student,
                'last_hw_project': latest_hw_project,
                'last_cw_project': latest_cw_project,
            })
        class_info.append({
        'class': section,
        'students': student_info
        })
            
    return render(request, 'teacher_dashboard.html', {
        'teacher': teacher,
        'classes': class_info
    })

@login_required
@teacher_required
def admin_dashboard(request):
    student_form = StudentCreationForm()
    teacher_form = TeacherCreationForm()
    class_form = ClassCreationForm()
    curriculum_form = CurriculumCreationForm()
    student_password_form = StudentPasswordResetForm()
    teacher_password_form = TeacherPasswordResetForm()

    classes = Class.objects.all().order_by('location', 'day', 'time')
    if request.user.teacher.is_admin:
        teacher = Teacher.objects.get(user = request.user)
        if request.method == 'POST':
            if 'create_student' in request.POST:
                student_form = StudentCreationForm(request.POST)
                if student_form.is_valid():
                    student_form.save()
                    return redirect('admin_dashboard')
            elif 'create_teacher' in request.POST:
                teacher_form = TeacherCreationForm(request.POST)
                if teacher_form.is_valid():
                    teacher_form.save()
                    return redirect('admin_dashboard')
        
            elif 'create_class' in request.POST:
                class_form = ClassCreationForm(request.POST)
                if class_form.is_valid():
                    class_form.save()
                    return redirect('admin_dashboard')
            
            elif 'reset_student_password' in request.POST:
                student_password_form = StudentPasswordResetForm(request.POST)
                if student_password_form.is_valid():
                    student = student_password_form.cleaned_data['student']
                    new_password = student_password_form.cleaned_data['new_password']
                    user = student.user
                    user.set_password(new_password)
                    user.save()
                    return redirect('admin_dashboard')
            elif 'reset_teacher_password' in request.POST:
                teacher_password_form = TeacherPasswordResetForm(request.POST)
                if teacher_password_form.is_valid():
                    teacher = teacher_password_form.cleaned_data['teacher']
                    new_password = teacher_password_form.cleaned_data['new_password']
                    user = teacher.user
                    user.set_password(new_password)
                    user.save()
                    return redirect('admin_dashboard')
                else:
                    print("Invalid teacher password form:", teacher_password_form.errors)
            elif 'create_curriculum' in request.POST:
                curriculum_form = CurriculumCreationForm(request.POST)
                if curriculum_form.is_valid():
                    curriculum_form.save()
                    return redirect('admin_dashboard')
        
        return render(request, 'admin_dashboard.html', {'student_form':student_form, 'teacher_form':teacher_form, 'class_form':class_form, 'classes':classes, 
                                                        'student_password_form': student_password_form, 'teacher_password_form': teacher_password_form, 'curriculum_form': curriculum_form, 'teacher': teacher} )
    else:
        return redirect('login')

@login_required
@teacher_required
def admin_class_view(request, class_id):
    if not request.user.teacher.is_admin:
        return redirect('teacher_dashboard')

    teacher = request.user.teacher
    class_obj = get_object_or_404(Class, id=class_id)

    if request.method == "POST":
        student_form = ClassStudentUpdateForm(request.POST, instance=class_obj)
        if student_form.is_valid():
            students = student_form.cleaned_data['students']

            class_obj.students.clear()  # cleaner than manual remove loop

            for student in students:
                student.classes.add(class_obj)
            return redirect('admin_class_view', class_id=class_obj.id)
    else:
        student_form = ClassStudentUpdateForm(instance=class_obj)

    return render(
        request,
        'admin_class_view.html',
        {
            'class_obj': class_obj,
            'student_form': student_form,
            'teacher': teacher
        }
    )


@login_required
@teacher_required
def view_student(request, username):

    teacher = Teacher.objects.get(user = request.user)
    student = get_object_or_404(Student, user__username = username)

    classes = student.classes.filter(teacher = teacher)

    if not classes.exists():
        raise Http404("No Student matches the given query.")

    student_projects = []
    for section in classes:
        hw_projects = (
            CodeProject.objects
            .filter(
                owner=student.user,
                for_class=section,
                assignment__isnull=False
            )
            .order_by("-last_edited")
        )

        cw_projects = (
            CodeProject.objects
            .filter(
                owner=student.user,
                for_class=section,
                assignment__isnull=True
            )
            .order_by("-last_edited")
        )

        student_projects.append({
            "class": section,
            "hw_projects": hw_projects,
            "cw_projects": cw_projects,
        })

    return render(request, "view_student.html", {
        "student": student,
        "teacher": teacher,
        "student_projects": student_projects,
    })
@login_required
@teacher_required
def create_assignment(request):
    teacher = Teacher.objects.get(user=request.user)

    class_id = request.GET.get("class")
    selected_class = None
    selected_curriculum = None

    if class_id:
        selected_class = get_object_or_404(
            Class,
            id=class_id,
            teacher=teacher
        )
        selected_curriculum = selected_class.curriculum

    curricula = Curriculum.objects.filter(
        classes__teacher=teacher
    ).distinct()

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        curriculum_id = request.POST.get("curriculum")

        curriculum = get_object_or_404(Curriculum, id=curriculum_id)

        assignment = Assignment.objects.create(
            created_by=teacher,
            curriculum=curriculum,
            title=title,
            description=description,
        )
        if selected_class:
            due_date = request.POST.get("due_date")
            if due_date:
                AssignedToClass.objects.create(
                    assignment=assignment,
                    for_class=selected_class,
                    due_date=due_date
                )

                return redirect(
                    "teacher_class_view",
                    class_code=selected_class.code
                )

        return redirect(
            "teacher_assignment_detail", assignment_id=assignment.id
        )

    return render(request, "create_assignment.html", {"curricula": curricula, "selected_curriculum": selected_curriculum,
        "selected_class": selected_class
    })
@login_required
@teacher_required
def teacher_assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, created_by__user=request.user)
    assigned_classes = assignment.assigned_instances.select_related("for_class")

    return render(request, "teacher_assignment_detail.html", {
        "assignment": assignment,
        "assigned_classes": assigned_classes,
    })

@login_required
@teacher_required
def assign_assignment_to_class(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, created_by__user=request.user)
    classes = request.user.teacher.classes.all()

    if request.method == "POST":
        class_id = request.POST.get("class_id")
        due_date = request.POST.get("due_date")

        class_obj = get_object_or_404(Class, id=class_id, teacher=request.user.teacher)

        AssignedToClass.objects.create(
            assignment=assignment,
            for_class=class_obj,
            due_date=due_date
        )

        return redirect("teacher_assignment_detail", assignment_id=assignment.id)

    return render(request, "assign_to_class.html", {
        "assignment": assignment,
        "classes": classes,
    })

@login_required
@teacher_required
def teacher_view_submissions(request, assigned_id):
    assigned = get_object_or_404(AssignedToClass, id=assigned_id, assignment__created_by__user=request.user)
    projects = (
        CodeProject.objects
        .filter(
            assignment=assigned.assignment,
            for_class=assigned.for_class
        )
        .select_related("owner")
    )

    submissions = defaultdict(list)

    students = assigned.for_class.students.all()

    projects_by_student = defaultdict(list)

    for project in projects:
        projects_by_student[project.owner].append(project)

    for student in students:
        submissions[student.user] = projects_by_student.get(student.user, [])

    return render(request, "teacher_view_submissions.html", {
        "assigned": assigned,
        "submissions": dict(submissions),
    })


@login_required
@student_required
def submit_assignment(request, assigned_id):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=400)

    assigned = get_object_or_404(AssignedToClass, id=assigned_id)
    student = request.user.student

    if assigned.for_class not in student.classes.all():
        return JsonResponse({"ok": False}, status=403)

    project = get_object_or_404(
        CodeProject,
        owner=request.user,
        assignment=assigned.assignment,
        for_class=assigned.for_class
    )

    project.submitted = True
    project.submitted_at = timezone.now()
    project.save()


    return JsonResponse({"ok": True})

@login_required
@student_required
def student_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code)
    student = request.user.student
    
    if class_obj not in student.classes.all():
        return redirect('student_dashboard')

    assigned_assignments = AssignedToClass.objects.filter(for_class = class_obj).select_related('assignment').order_by('due_date')
    submitted_ids = set(
        CodeProject.objects.filter(
            owner=request.user,
            for_class = class_obj,
            submitted = True,
            assignment__isnull=False
        )
        .values_list("assignment_id", flat=True)
    )
    return render(request, 'student_class_view.html', {
        'class': class_obj,
        'assigned_assignments': assigned_assignments,
        'submitted_ids': submitted_ids
    })

@login_required
@teacher_required
def teacher_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code, teacher = request.user.teacher)
    
    assigned_assignments = (
        AssignedToClass.objects
        .filter(for_class=class_obj)
        .select_related("assignment")
        .order_by("due_date")
    )
    assigned_assignment_ids = set(
        assigned_assignments.values_list("assignment_id", flat=True)
    )

    available_assignments = Assignment.objects.filter(
        curriculum=class_obj.curriculum,
        created_by=request.user.teacher
    )

    students = class_obj.students.all()

    return render(request, "teacher_class_view.html", {
        "class": class_obj,
        "assigned_assignments": assigned_assignments,
        "available_assignments": available_assignments,
        "assigned_assignment_ids": assigned_assignment_ids,
        "students": students
    })

def healthz(request):
    """
    Simple health check endpoint.
    Returns {"ok": True} if app and DB respond.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 500
    return JsonResponse({"ok": db_ok}, status=status)

@login_required
def editor_view(request):
    user = request.user
    is_json = "application/json" in request.headers.get("content-type", "")

    assigned_id = request.GET.get("assigned_id")
    assigned = None
    project_id = request.GET.get("project_id")

    selected_file = request.GET.get("file")

    # Assignment context (if present)
    if assigned_id:
        assigned = get_object_or_404(AssignedToClass, id=assigned_id)

        # Security: student must belong to class
        if hasattr(user, "student"):
            if assigned.for_class not in user.student.classes.all():
                return HttpResponse("Access denied", status=403)

    # Load initial code (assignment)
    initial_code = ""
    code_name = ""
    selected_class_id = None
    is_readonly = False
    project = None

    if project_id:
        project = get_object_or_404(CodeProject, id=project_id)

        if hasattr(request.user, "teacher"):
            if project.for_class.teacher != request.user.teacher:
                print("access denied: teacher does not match project class teacher")
                return HttpResponse("Access denied", status=403)
        else:
            if project.owner != request.user:
                return HttpResponse("Access denied", status=403)
        if project.assignment and project.for_class:
            assigned = AssignedToClass.objects.filter(
                assignment=project.assignment,
                for_class=project.for_class
            ).first()
        
        project_file = None

        if selected_file:
            project_file = project.files.filter(path=selected_file).first()

        if not project_file:
            project_file = project.files.filter(path="main.py").first()

        if not project_file:
            project_file = project.files.first()

        if project_file:
            try:
                project_file.file.open("rb")
                initial_code = force_str(project_file.file.read(), errors="ignore")
            except Exception:
                initial_code = ""

            code_name = project_file.path

        if project.submitted:
            is_readonly = True

    elif assigned:
        project = get_or_create_editor_project(
            user=user,
            for_class=assigned.for_class,
            assignment=assigned.assignment
        )

        ensure_main_file(project)

        main_file = project.files.filter(path="main.py").first()
        
        try:
            main_file.file.open("rb")
            initial_code = force_str(main_file.file.read(), errors="ignore")
        except Exception:
            initial_code = ""
        
        code_name = main_file.path
        selected_class_id = str(assigned.for_class.id)
    else:
        project = None
    # JSON AUTOSAVE (editor autosave)
    if request.method == "POST" and is_json:
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

        code = data.get("code", "")
        path = data.get("path", "main.py")
        project_id = data.get("project_id")
        if not project_id:
            return JsonResponse({"ok": False, "error": "Missing project_id"}, status=400)

        project = get_object_or_404(CodeProject, id=project_id)
        if project.owner != user:
            return JsonResponse({"ok": False, "error": "Access denied"}, status=403)
        
        project_file, _ = ProjectFile.objects.get_or_create(
            project=project,
            path=path,
        )

        project_file.file.save(
            path,
            ContentFile(code.encode()),
            save=True
        )
        project.last_edited = timezone.now()
        project.save(update_fields=["last_edited"])

        return JsonResponse({
            "ok": True,
            "project_id": project.id if project else "",
            "path": project_file.path,
            "last_edited": project_file.last_edited.timestamp()
        })

    # Class dropdown options
    if hasattr(user, "teacher"):
        class_options = user.teacher.classes.all()
    elif hasattr(user, "student"):
        class_options = user.student.classes.all()
    else:
        class_options = []

    projects = CodeProject.objects.filter(owner=request.user).select_related("for_class")

    grouped = defaultdict(list)

    for p in projects:
        if p.for_class:
            grouped[p.for_class].append(p)

    sorted_classes = sorted(
        grouped.items(),
        key=lambda item: max([proj.last_edited for proj in item[1]]) if item[1] else timezone.now(),
        reverse=True
    )

    return render(request, "editor_view.html", {
        "user": user,
        "initial_code": initial_code,
        "code_name": code_name,
        "assigned": assigned,
        "is_readonly": is_readonly,
        "project_id": project.id if project else "",
        "is_submitted": project.submitted if project else False,
    })

def get_or_create_editor_project(user, for_class=None, assignment=None):

    DEFAULT_CODE = """# Write your Python code here

print("Hello World!")
"""

    project_name = "Classwork"
    if assignment:
        project_name = assignment.title
    project, _ = CodeProject.objects.get_or_create(
        owner=user,
        for_class=for_class,
        assignment = assignment,
        defaults={"name": project_name}
    )
    main_file, created = ProjectFile.objects.get_or_create(
        project=project,
        path="main.py",
    )

    if created or not main_file.file:
        main_file.file.save("main.py", ContentFile(DEFAULT_CODE), save=True)
    return project

def get_project_files(request, project_id):
    project = get_object_or_404(CodeProject, id=project_id)

    if project.owner != request.user:
        return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

    files = {}
    for pf in project.files.order_by("path"):
        try:
            pf.file.open("rb")
            files[pf.path] = force_str(pf.file.read(), errors="ignore")
        except:
            files[pf.path] = ""

    return JsonResponse({"ok": True, "files": files})

@login_required
def editor_projects(request):
    if hasattr(request.user, "teacher"):
        user_classes = request.user.teacher.classes.all().order_by("name")
    elif hasattr(request.user, "student"):
        user_classes = request.user.student.classes.all().order_by("name")
    else:
        user_classes = Class.objects.none()

    projects = (
        CodeProject.objects
        .filter(owner=request.user, for_class__in=user_classes)
        .select_related("for_class")
        .prefetch_related("files")
        .order_by("name")
    )

    projects_by_class_id = defaultdict(list)

    for project in projects:
        projects_by_class_id[project.for_class_id].append({
            "id": project.id,
            "name": project.name or "Untitled Project",
            "files": list(project.files.values_list("path", flat=True)),
            "assignment_id": project.assignment_id,
        })

    result = []
    for class_obj in user_classes:
        result.append({
            "id": class_obj.id,
            "name": class_obj.name,
            "projects": projects_by_class_id[class_obj.id],
        })

    return JsonResponse({
        "classes": result
    })

@login_required
def create_editor_project(request):

    if request.method != "POST":
        return HttpResponseBadRequest()

    data = json.loads(request.body)

    name = data.get("name")

    if not name:
        return JsonResponse({"ok": False})

    class_id = data.get("class_id")

    if not class_id:
        return JsonResponse({"ok": False, "error": "Missing class_id"})

    class_obj = get_object_or_404(Class, id=class_id)

    project = CodeProject.objects.create(
    owner=request.user,
    name=name,
    for_class=class_obj,
    assignment=None
    )

    ensure_main_file(project)

    return JsonResponse({
        "ok": True,
        "project_id": project.id
    })

def ensure_main_file(project):
    DEFAULT_CODE = """# Write your Python code here

print("Hello World!")
"""

    main_file, created = ProjectFile.objects.get_or_create(
        project=project,
        path="main.py",
    )

    if created or not main_file.file:
        main_file.file.save("main.py", ContentFile(DEFAULT_CODE), save=True)

@login_required
def editor_project_file(request, project_id, file_path):

    project = get_object_or_404(
        CodeProject,
        id=project_id,
        owner=request.user
    )

    pf = get_object_or_404(
        ProjectFile,
        project=project,
        path=file_path
    )

    try:
        pf.file.open("rb")
        code = force_str(pf.file.read(), errors="ignore")
    except Exception:
        code = ""

    return JsonResponse({
        "ok": True,
        "code": code
    })

@login_required
def create_project_file(request, project_id):

    if request.method != "POST":
        return HttpResponseBadRequest()

    data = json.loads(request.body)

    path = data.get("path")

    if not path:
        return JsonResponse({"ok": False})
    
    if not path.endswith(".py"):
        path += ".py"

    project = get_object_or_404(
        CodeProject,
        id=project_id,
        owner=request.user
    )

    file, created = ProjectFile.objects.get_or_create(
        project=project,
        path=path
    )

    if created:
        file.file.save(path, ContentFile(b""), save=True)

    return JsonResponse({
        "ok": True,
        "created": created
    })

@login_required
@csrf_exempt
def rename_file(request, project_id):
    data = json.loads(request.body)

    oldPath = data.get("old_path")
    newPath = data.get("new_path")

    if not newPath.endswith(".py"):
        newPath += ".py"


    project = get_object_or_404(CodeProject, id=project_id, owner=request.user)
    old_file = get_object_or_404(ProjectFile, project=project, path=oldPath)

    if ProjectFile.objects.filter(project=project, path=newPath).exists():
        return JsonResponse({"ok": False, "error": "File already exists"})
    try:
        old_file.file.open("rb")
        content = old_file.file.read()
    except Exception:
        content = b""

    new_file = ProjectFile.objects.create(
        project=project,
        path=newPath,
    )

    new_file.file.save(newPath, ContentFile(content), save=True)

    old_file.file.delete(save=False)
    old_file.delete()

    return JsonResponse({"ok": True})
@login_required
@csrf_exempt
def delete_file(request, project_id):
    data = json.loads(request.body)

    path = data.get("path")

    project = get_object_or_404(CodeProject, id=project_id, owner=request.user)
    file = get_object_or_404(ProjectFile, project=project, path=path)
    file.delete()
    return JsonResponse({"ok": True})

@login_required
@csrf_exempt
def move_file(request):
    data = json.loads(request.body)
    from_project_id = data.get("from_project")
    to_project_id = data.get("to_project")
    path = data.get("path")

    from_project = get_object_or_404(CodeProject, id=from_project_id, owner=request.user)
    to_project = get_object_or_404(CodeProject, id=to_project_id, owner=request.user)

    file = get_object_or_404(ProjectFile, project=from_project, path=path)

    if ProjectFile.objects.filter(project=to_project, path=path).exists():
        return JsonResponse({"ok": False, "error": "File already exists in target project"})
    
    file.project = to_project
    file.save()

    return JsonResponse({"ok": True})

@login_required
@teacher_required
def get_project_files_for_teacher(request, project_id):
    project = get_object_or_404(CodeProject, id=project_id)

    if project.for_class.teacher != request.user.teacher:
        return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

    files = {}

    for pf in project.files.all():
        try:
            pf.file.open("rb")
            files[pf.path] = force_str(pf.file.read(), errors="ignore")
        except:
            files[pf.path] = ""

    return JsonResponse({
        "ok": True,
        "project_name": project.name,
        "files": files
    })