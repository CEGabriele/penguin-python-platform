from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from .forms import StudentCreationForm, TeacherCreationForm, CurriculumCreationForm, ClassCreationForm, ClassEditForm, StudentPasswordResetForm, TeacherPasswordResetForm, generate_unique_username
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
import time
import logging
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

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

    # Add orphaned projects (from deleted classes)
    orphaned_projects = CodeProject.objects.filter(
        owner=user,
        for_class__isnull=True
    ).order_by("-last_edited")

    return render(request, 'student_dashboard.html', {
        'student': student,
        'classes': classes,
        'orphaned_projects': orphaned_projects
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
@require_GET
def check_duplicate_student(request):
    if not request.user.teacher.is_admin:
        return HttpResponseBadRequest()

    first_name = request.GET.get('first_name', '').strip()
    last_name = request.GET.get('last_name', '').strip()
    if not (first_name and last_name):
        return JsonResponse({'matches': []})

    matches = (
        Student.objects
        .filter(user__first_name__iexact=first_name, user__last_name__iexact=last_name)
        .select_related('user')
        .prefetch_related('classes')
        .order_by('user__username')
    )

    return JsonResponse({
        'matches': [
            {
                'full_name': m.user.get_full_name(),
                'username': m.user.username,
                'classes': [f"{c.name} ({c.location})" for c in m.classes.all()],
            }
            for m in matches
        ],
        'resulting_username': generate_unique_username(first_name, last_name),
    })


@login_required
@teacher_required
@require_GET
def check_duplicate_teacher(request):
    if not request.user.teacher.is_admin:
        return HttpResponseBadRequest()

    first_name = request.GET.get('first_name', '').strip()
    last_name = request.GET.get('last_name', '').strip()
    if not (first_name and last_name):
        return JsonResponse({'matches': []})

    matches = (
        Teacher.objects
        .filter(user__first_name__iexact=first_name, user__last_name__iexact=last_name)
        .select_related('user')
        .prefetch_related('classes')
        .order_by('user__username')
    )

    return JsonResponse({
        'matches': [
            {
                'full_name': m.user.get_full_name(),
                'username': m.user.username,
                'classes': [f"{c.name} ({c.location})" for c in m.classes.all()],
            }
            for m in matches
        ],
        'resulting_username': generate_unique_username(first_name, last_name),
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
                    new_class = class_form.save()
                    return redirect('add_students_to_class', class_id=new_class.id)
            
            elif 'reset_student_password' in request.POST:
                student_password_form = StudentPasswordResetForm(request.POST)
                if student_password_form.is_valid():
                    student = student_password_form.cleaned_data['student']
                    new_password = student_password_form.cleaned_data['new_password']
                    user = student.user
                    user.set_password(new_password)
                    user.save()
                    student.password_text = new_password
                    student.save()
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

    # Handle removing a student
    if request.method == "POST" and "remove_student" in request.POST:
        student_id = request.POST.get("remove_student")
        student = get_object_or_404(Student, id=student_id)
        student.classes.remove(class_obj)
        return redirect('admin_class_view', class_id=class_obj.id)

    # Handle adding assignments to the class
    if request.method == "POST" and "assign_assignment" in request.POST:
        assignment_id = request.POST.get("assignment_id")
        due_date = request.POST.get("due_date")

        assignment = get_object_or_404(Assignment, id=assignment_id)

        # Check if already assigned
        if not AssignedToClass.objects.filter(
            assignment=assignment,
            for_class=class_obj
        ).exists():
            AssignedToClass.objects.create(
                assignment=assignment,
                for_class=class_obj,
                due_date=due_date
            )

        return redirect('admin_class_view', class_id=class_obj.id)

    # Get assigned assignments
    assigned_assignments = class_obj.assigned_assignments.select_related("assignment")

    # Get available assignments to assign
    all_assignments = Assignment.objects.all()
    already_assigned_ids = set(
        assigned_assignments.values_list("assignment_id", flat=True)
    )
    available_assignments = all_assignments.exclude(id__in=already_assigned_ids)

    return render(
        request,
        'admin_class_view.html',
        {
            'class_obj': class_obj,
            'teacher': teacher,
            'assigned_assignments': assigned_assignments,
            'available_assignments': available_assignments,
        }
    )


@login_required
@teacher_required
def add_students_to_class(request, class_id):
    if not request.user.teacher.is_admin:
        return redirect('teacher_dashboard')

    class_obj = get_object_or_404(Class, id=class_id)
    query = request.GET.get('q', '').strip()

    # Handle adding a single student (POST request)
    if request.method == "POST":
        student_id = request.POST.get('add_student')
        student = get_object_or_404(Student, id=student_id)
        student.classes.add(class_obj)
        # Stay on the search page to allow adding multiple students
        return redirect('add_students_to_class', class_id=class_obj.id)

    # Search for students
    if query:
        students = Student.objects.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query)
        ).select_related('user').order_by('user__first_name', 'user__last_name')
    else:
        students = Student.objects.select_related('user').order_by('user__first_name', 'user__last_name')

    # Get currently enrolled students
    current_student_ids = set(class_obj.students.values_list('id', flat=True))

    # Filter out already enrolled students from the list
    available_students = [s for s in students if s.id not in current_student_ids]

    return render(
        request,
        'add_students_to_class.html',
        {
            'class_obj': class_obj,
            'students': available_students,
            'query': query,
        }
    )


@login_required
@teacher_required
def edit_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    teacher = request.user.teacher

    # Check permission: must be admin or the teacher who owns the class
    if not (teacher.is_admin or class_obj.teacher == teacher):
        return redirect('teacher_dashboard')

    if request.method == "POST":
        form = ClassEditForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            return redirect('admin_class_view', class_id=class_obj.id)
    else:
        form = ClassEditForm(instance=class_obj)

    return render(
        request,
        'edit_class.html',
        {
            'form': form,
            'class_obj': class_obj,
            'teacher': teacher
        }
    )


@login_required
@teacher_required
def delete_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    teacher = request.user.teacher

    # Check permission: must be admin or the teacher who owns the class
    if not (teacher.is_admin or class_obj.teacher == teacher):
        return redirect('teacher_dashboard')

    if request.method == "POST":
        # Detach all projects from this class instead of deleting them
        CodeProject.objects.filter(for_class=class_obj).update(for_class=None)
        class_obj.delete()
        return redirect('teacher_dashboard')

    return render(
        request,
        'confirm_delete_class.html',
        {'class_obj': class_obj}
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
def admin_create_assignment(request):
    teacher = Teacher.objects.get(user=request.user)

    if not teacher.is_admin:
        return redirect('teacher_dashboard')

    # Admins can see all curricula
    curricula = Curriculum.objects.all()

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

        return redirect("teacher_assignment_detail", assignment_id=assignment.id)

    return render(request, "admin_create_assignment.html", {"curricula": curricula})


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
    assignment = get_object_or_404(Assignment, id=assignment_id)
    teacher = request.user.teacher

    # Check permission: must be admin or the teacher who created it
    if not (teacher.is_admin or assignment.created_by == teacher):
        return redirect('teacher_dashboard')

    assigned_classes = assignment.assigned_instances.select_related("for_class")

    return render(request, "teacher_assignment_detail.html", {
        "assignment": assignment,
        "assigned_classes": assigned_classes,
    })

@login_required
@teacher_required
def assign_assignment_to_class(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    teacher = request.user.teacher

    # Check permission: must be admin or the teacher who created it
    if not (teacher.is_admin or assignment.created_by == teacher):
        return redirect('teacher_dashboard')

    # If admin, show all classes; otherwise show only their classes
    if teacher.is_admin:
        classes = Class.objects.all()
    else:
        classes = teacher.classes.all()

    if request.method == "POST":
        class_id = request.POST.get("class_id")
        due_date = request.POST.get("due_date")

        class_obj = get_object_or_404(Class, id=class_id)

        # Admin can assign to any class; regular teachers only to their own
        if not (teacher.is_admin or class_obj.teacher == teacher):
            return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

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
    assigned = get_object_or_404(AssignedToClass, id=assigned_id)
    teacher = request.user.teacher

    # Check permission: must be admin or the teacher who created the assignment or owns the class
    if not (teacher.is_admin or
            assigned.assignment.created_by == teacher or
            assigned.for_class.teacher == teacher):
        return redirect('teacher_dashboard')

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
    Comprehensive health check endpoint.
    Returns component status (DB, S3, API latency, submission processing).
    All checks complete within 5 seconds with short timeouts.
    """
    from datetime import datetime
    start_time = time.time()

    health = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "db_ok": False,
        "s3_ok": False,
        "recent_submissions_processed": 0,
        "error_rate_5min_percent": 0.0,
        "all_ok": False,
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        health["db_ok"] = True
    except Exception as e:
        logger.error(f"Health check: DB connection failed: {e}")
        health["db_ok"] = False

    if getattr(settings, 'USE_S3', False):
        try:
            import boto3
            from botocore.exceptions import ClientError

            bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
            if not bucket_name:
                raise ValueError("AWS_STORAGE_BUCKET_NAME not configured")

            s3 = boto3.client(
                "s3",
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
            )
            s3.head_bucket(Bucket=bucket_name)
            health["s3_ok"] = True
        except Exception as e:
            logger.error(f"Health check: S3 connection failed: {e}")
            health["s3_ok"] = False
    else:
        health["s3_ok"] = True

    try:
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)
        recent_submitted = CodeProject.objects.filter(
            submitted=True,
            submitted_at__gte=one_hour_ago
        ).count()
        health["recent_submissions_processed"] = recent_submitted
    except Exception as e:
        logger.error(f"Health check: Submission query failed: {e}")
        health["recent_submissions_processed"] = 0

    # App is healthy if database is OK (S3 is optional)
    health["all_ok"] = health["db_ok"]
    status = 200 if health["all_ok"] else 500

    logger.info(f"Health check: {json.dumps(health)}")
    return JsonResponse(health, status=status)

@csrf_exempt
@require_GET
def active_workers_metrics(request):
    """
    Returns count of active code execution workers.
    Workers send heartbeats while code is running; entries expire after 60 seconds.
    Public endpoint (no auth required) for monitoring systems to scrape.
    """
    from django.core.cache import cache

    active_workers_dict = cache.get("active_workers_registry", {})
    now = timezone.now().timestamp()

    # Remove expired entries (older than 70 seconds, giving 10s buffer)
    active_workers_dict = {
        worker_id: timestamp
        for worker_id, timestamp in active_workers_dict.items()
        if now - timestamp < 70
    }

    return JsonResponse({
        "timestamp": timezone.now().isoformat() + "Z",
        "active_workers": len(active_workers_dict),
        "workers": list(active_workers_dict.keys()),
    }, status=200)

@csrf_exempt
@require_GET
def active_users_metrics(request):
    """
    Returns users with recent activity (code edits in last N minutes).
    Activity is determined by CodeProject.last_edited, not login sessions.
    Query param: ?minutes=15 (default) to adjust activity window.
    Public endpoint for monitoring systems.
    """
    from django.contrib.auth.models import User
    import json

    try:
        now = timezone.now()
        recently_active_minutes = int(request.GET.get("minutes", 15))
        time_threshold = now - timedelta(minutes=recently_active_minutes)

        # Users who edited code recently
        recently_active_user_ids = set(
            CodeProject.objects
            .filter(last_edited__gte=time_threshold)
            .values_list("owner_id", flat=True)
            .distinct()
        )

        # Count by role
        recently_active_students = User.objects.filter(
            id__in=recently_active_user_ids,
            student__isnull=False
        ).count()
        recently_active_teachers = User.objects.filter(
            id__in=recently_active_user_ids,
            teacher__isnull=False
        ).count()

        total_users = User.objects.filter(is_active=True).count()
        students_total = User.objects.filter(student__isnull=False).count()
        teachers_total = User.objects.filter(teacher__isnull=False).count()

        return JsonResponse({
            "timestamp": timezone.now().isoformat() + "Z",
            "activity_window_minutes": recently_active_minutes,
            "recently_active": len(recently_active_user_ids),
            "recently_active_students": recently_active_students,
            "recently_active_teachers": recently_active_teachers,
            "total_users": total_users,
            "students": students_total,
            "teachers": teachers_total,
        }, status=200)
    except Exception as e:
        logger.error(f"Active users metrics error: {e}")
        return JsonResponse({"error": "Failed to fetch metrics"}, status=500)

@csrf_exempt
@require_GET
def instance_status_metrics(request):
    """
    Returns instance status: memory, CPU, uptime.
    Public endpoint for monitoring systems.
    """
    import psutil
    import platform
    from datetime import datetime
    import os

    try:
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()

        # Process info (Django process)
        process = psutil.Process(os.getpid())
        process_memory_mb = process.memory_info().rss / (1024 * 1024)

        return JsonResponse({
            "timestamp": timezone.now().isoformat() + "Z",
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "process_memory_mb": round(process_memory_mb, 2),
            "uptime_seconds": int(uptime_seconds),
            "python_version": platform.python_version(),
            "platform": platform.system(),
        }, status=200)
    except Exception as e:
        logger.error(f"Instance status metrics error: {e}")
        return JsonResponse({"error": "Failed to fetch metrics"}, status=500)

@csrf_exempt
def worker_heartbeat(request):
    """
    Receives heartbeat from a code execution worker.
    - GET with ?worker_id=xxx&action=start : marks worker as active for 60s
    - GET with ?worker_id=xxx&action=stop : removes worker immediately

    Workers send heartbeats every 10s while code runs to keep the 60s timer fresh.
    No authentication required (workers are client-side, can't authenticate).
    """
    from django.core.cache import cache

    worker_id = request.GET.get("worker_id")
    action = request.GET.get("action", "start")

    if not worker_id:
        return JsonResponse({"error": "worker_id required"}, status=400)

    active_workers_dict = cache.get("active_workers_registry", {})

    if action == "stop":
        active_workers_dict.pop(worker_id, None)
    else:  # start
        active_workers_dict[worker_id] = timezone.now().timestamp()

    cache.set("active_workers_registry", active_workers_dict, timeout=3600)
    return JsonResponse({"status": "active" if action == "start" else "stopped"}, status=200)

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
            # Teachers can only view projects from their classes
            if project.for_class and project.for_class.teacher != request.user.teacher:
                print("access denied: teacher does not match project class teacher")
                return HttpResponse("Access denied", status=403)
        else:
            # Students can only view their own projects
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
            "last_edited": project.last_edited.isoformat() if project.last_edited else None,
        })

    # Get projects from deleted classes
    orphaned_projects = (
        CodeProject.objects
        .filter(owner=request.user, for_class__isnull=True)
        .prefetch_related("files")
        .order_by("name")
    )

    orphaned_list = []
    for project in orphaned_projects:
        orphaned_list.append({
            "id": project.id,
            "name": project.name or "Untitled Project",
            "files": list(project.files.values_list("path", flat=True)),
            "assignment_id": project.assignment_id,
            "last_edited": project.last_edited.isoformat() if project.last_edited else None,
        })

    result = []
    for class_obj in user_classes:
        result.append({
            "id": class_obj.id,
            "name": class_obj.name,
            "projects": projects_by_class_id[class_obj.id],
        })

    # Add projects  section if any exist
    if orphaned_list:
        result.append({
            "id": None,
            "name": "Archived Projects (Deleted Classes)",
            "projects": orphaned_list,
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


@login_required
def project_feedback(request, project_id):
    project = get_object_or_404(CodeProject, id=project_id)

    if request.method == "GET":
        # Auth: teacher of the class or the student owner
        is_teacher = (
            hasattr(request.user, "teacher")
            and project.for_class
            and project.for_class.teacher == request.user.teacher
        )
        is_student_owner = project.owner == request.user

        if not (is_teacher or is_student_owner):
            return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

        # Mark feedback as read if student is viewing
        if is_student_owner:
            try:
                feedback = project.feedback
                feedback.read_by_student = True
                feedback.save()
            except ProjectFeedback.DoesNotExist:
                pass

        feedback_data = {"overall": None, "line_comments": []}

        # Get overall feedback
        try:
            fb = project.feedback
            feedback_data["overall"] = {
                "comment": fb.comment,
                "grader_name": fb.grader.user.get_full_name(),
                "created_at": fb.created_at.isoformat(),
                "updated_at": fb.updated_at.isoformat(),
            }
        except ProjectFeedback.DoesNotExist:
            pass

        # Get line comments
        for lc in project.line_comments.all():
            feedback_data["line_comments"].append({
                "id": lc.id,
                "file_path": lc.file_path,
                "line_number": lc.line_number,
                "end_line": lc.end_line or lc.line_number,
                "comment": lc.comment,
                "grader_name": lc.grader.user.get_full_name(),
                "created_at": lc.created_at.isoformat(),
                "updated_at": lc.updated_at.isoformat(),
            })

        return JsonResponse({"ok": True, **feedback_data})

    elif request.method == "POST":
        # Auth: teacher only
        if not hasattr(request.user, "teacher"):
            return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

        if project.for_class.teacher != request.user.teacher:
            return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

        try:
            data = json.loads(request.body)
            comment = data.get("comment", "")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

        feedback, created = ProjectFeedback.objects.get_or_create(
            project=project,
            defaults={"grader": request.user.teacher}
        )
        feedback.comment = comment
        feedback.save()

        return JsonResponse({
            "ok": True,
            "feedback": {
                "comment": feedback.comment,
                "grader_name": feedback.grader.user.get_full_name(),
                "created_at": feedback.created_at.isoformat(),
                "updated_at": feedback.updated_at.isoformat(),
            }
        })

    return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)


@login_required
@teacher_required
def save_line_comment(request, project_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    project = get_object_or_404(CodeProject, id=project_id)

    # Auth: teacher of the class
    if project.for_class.teacher != request.user.teacher:
        return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

    try:
        data = json.loads(request.body)
        file_path = data.get("file_path")
        line_number = data.get("line_number")
        end_line = data.get("end_line", line_number)
        comment = data.get("comment", "")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    if not file_path or line_number is None:
        return JsonResponse({"ok": False, "error": "Missing file_path or line_number"}, status=400)

    if end_line is None or end_line < line_number:
        end_line = line_number

    line_comment, created = CodeLineComment.objects.update_or_create(
        project=project,
        file_path=file_path,
        line_number=line_number,
        defaults={"comment": comment, "end_line": end_line, "grader": request.user.teacher}
    )

    return JsonResponse({
        "ok": True,
        "line_comment": {
            "id": line_comment.id,
            "file_path": line_comment.file_path,
            "line_number": line_comment.line_number,
            "end_line": line_comment.end_line or line_comment.line_number,
            "comment": line_comment.comment,
            "grader_name": line_comment.grader.user.get_full_name(),
            "created_at": line_comment.created_at.isoformat(),
            "updated_at": line_comment.updated_at.isoformat(),
        }
    })


@login_required
@teacher_required
def delete_line_comment(request, comment_id):
    if request.method != "DELETE":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    line_comment = get_object_or_404(CodeLineComment, id=comment_id)

    # Auth: the teacher who created the comment
    if line_comment.grader != request.user.teacher:
        return JsonResponse({"ok": False, "error": "Access denied"}, status=403)

    line_comment.delete()
    return JsonResponse({"ok": True})


@login_required
def operations_dashboard(request):
    """Operations dashboard for admins/staff only. Real-time health monitoring."""
    if not request.user.is_staff:
        return HttpResponse("Access denied", status=403)

    return render(request, "admin/operations_dashboard.html", {
        "healthz_url": "/healthz/",
    })


@login_required
def profile_view(request):
    user = request.user
    return render(request, 'profile.html', {
        'user': user,
    })


@login_required
def projects_view(request):
    user = request.user
    projects = CodeProject.objects.filter(owner=user).order_by('-last_edited')
    return render(request, 'projects.html', {
        'projects': projects,
    })


@login_required
def rename_project(request, project_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    project = get_object_or_404(CodeProject, id=project_id, owner=request.user)

    data = json.loads(request.body)
    new_name = data.get("name", "").strip()

    if not new_name:
        return JsonResponse({"ok": False, "error": "Project name cannot be empty"})

    project.name = new_name
    project.save()

    return JsonResponse({"ok": True, "name": project.name})


@login_required
def delete_project(request, project_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    project = get_object_or_404(CodeProject, id=project_id, owner=request.user)
    project.delete()

    return JsonResponse({"ok": True})