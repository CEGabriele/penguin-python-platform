from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from .forms import HomeworkUpload, ClassworkUpload, HomeworkTemplateForm, HomeworkQuestionFormSet, HomeworkChoiceFormSet, StudentAnswerForm, StudentCreationForm, TeacherCreationForm, CurriculumCreationForm, ClassCreationForm, ClassStudentUpdateForm, StudentPasswordResetForm, TeacherPasswordResetForm, AssignHomeworkDueDateForm
from .models import *
from django.contrib.auth.decorators import login_required
from itertools import groupby
from operator import attrgetter
from django.forms import modelformset_factory
from django.views.decorators.csrf import csrf_exempt
import json, os
import traceback
from dashboard.services.ai_hw_review import get_ai_review
from django.db.models import OuterRef, Exists, Count, Q
from collections import defaultdict
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist, SuspiciousFileOperation
from django.utils.text import slugify
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

try:
    from botocore.exceptions import ClientError
except Exception:
    ClientError = tuple()

def _related_or_none(obj, attr: str):
    try:
        return getattr(obj, attr)
    except ObjectDoesNotExist:
        return None

@login_required
@student_required
def student_dashboard(request):
    student = Student.objects.get(user = request.user) 
    user = request.user

    hw_files = user.uploads_set.filter(assignment__isnull=False)
    cw_files = user.uploads_set.filter(assignment__isnull=True)
    
    if request.method == 'POST' and 'uploaded_file' in request.FILES:
            uploaded_file = request.FILES["uploaded_file"]
            class_code = request.POST.get("class_code")

            class_obj = get_object_or_404(Class, code=class_code)

            Uploads.objects.create(
                person=user,
                for_class=class_obj,
                file=uploaded_file,
                display_name=uploaded_file.name,
            )

            return redirect("student_dashboard")

    
    classes = []
    
    for section in student.classes.all():
        class_uploads = Uploads.objects.filter(
            person=user,
            for_class=section,
        ).order_by("-last_edited")

        hw_files = class_uploads.filter(assignment__isnull=False)
        cw_files = class_uploads.filter(assignment__isnull=True)

        classes.append({
            'class': section,
            'hw_files': hw_files,
            'cw_files': cw_files,
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
            last_hw_file = student.latest_assignment_file(section)
            last_cw_file = student.latest_classwork_file(section)

            student_info.append({
                'student': student,
                'last_hw_file': last_hw_file,
                'last_cw_file': last_cw_file,
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
    if request.user.teacher.is_admin:
        teacher = Teacher.objects.get(user = request.user)
        class_obj = get_object_or_404(Class, id=class_id)
        student_form = ClassStudentUpdateForm(request.POST or None, instance = class_obj)

        if request.method and student_form.is_valid():
            students = student_form.cleaned_data['students']

            for student in class_obj.students.all():
                student.classes.remove(class_obj)

            for student in students:
                student.classes.add(class_obj)
            
            return redirect('admin_class_view', class_id = class_obj.id)

        return render(request, 'admin_class_view.html', {'class_obj': class_obj, 'student_form': student_form, 'teacher': teacher})
    else:
        return redirect('teacher_dashboard')
    


@login_required
@teacher_required
def view_student(request, username):

    teacher = Teacher.objects.get(user = request.user)
    student = Student.objects.get(user = User.objects.get(username = username))

    classes = student.classes.filter(teacher = teacher)

    student_files = []
    for section in classes:
        hw_files = student.user.uploads_set.filter(
            for_class=section,
            assignment__isnull=False,
        )

        cw_files = student.user.uploads_set.filter(
            for_class=section,
            assignment__isnull=True,
        )

        student_files.append({'class': section, 'hw_files': hw_files, 'cw_files': cw_files}) 
    return render(request, 'view_student.html', {'student': student, 'teacher': teacher, 'student_files': student_files, 'teacher': teacher})


@login_required
def download_file_view(request, file_id):

    upload = get_object_or_404(
        Uploads.objects.select_related("person", "for_class__teacher"),
        id=file_id,
    )

    user = request.user
    user_teacher = _related_or_none(user, "teacher")
    is_admin   = user.is_superuser
    is_owner   = (upload.person_id == user.id)    

    class_id  = getattr(upload.for_class, "teacher_id", None)
    is_teacher = (user_teacher is not None) and (class_id == getattr(user_teacher, "id", None))

    if not (is_admin or is_owner or is_teacher):
        raise Http404("Access denied")

    # Open and stream the file; map storage issues to 404 instead of 500
    try:
        upload.file.open("rb")
    except (FileNotFoundError, OSError, ValueError, SuspiciousFileOperation, ClientError):
        raise Http404("File not found on storage")

    return FileResponse(
        upload.file,
        as_attachment=True,
        filename=os.path.basename(upload.display_name or "download.bin"),
    )
    

@login_required
@student_required
def student_assignments(request):
    student = Student.objects.get(user = request.user)
    classes = student.classes.all()

    assignments = AssignedHomework.objects.filter(for_class__in=classes).select_related('template', 'for_class')

    completed_assignments = set(
        StudentQuestionResponse.objects
        .filter(student=student)
        .values_list('assigned_homework_id', flat=True)
        .distinct()
    )

    class_forms = defaultdict(lambda: {'completed': [], 'incomplete': []})

    for assigned in assignments:
        class_obj = assigned.for_class
        if assigned.id in completed_assignments:
            class_forms[class_obj]['completed'].append(assigned)
        else:
            class_forms[class_obj]['incomplete'].append(assigned)

    return render(request, 'student_assignments.html', {
        'class_forms': dict(class_forms)
    })


@login_required
@teacher_required
def teacher_assignments_list(request):
    teacher = Teacher.objects.get(user = request.user)
    classes = teacher.classes.all()
    assignments = (
        AssignedHomework.objects
        .filter(for_class__in = classes)
        .select_related('template', 'for_class')
        .annotate(num_submissions = Count('studentquestionresponse__student', distinct=True))
        .order_by('for_class__name', 'due_date')
    )

    class_forms = {class_obj: list(grouped_assignments)
                   for class_obj, grouped_assignments in groupby(assignments, key = attrgetter('for_class'))
    }

    return render(request, 'teacher_assignments_list.html', {'class_forms':class_forms, 'teacher': teacher})

@login_required
@teacher_required
def create_assignment(request):
    teacher = Teacher.objects.get(user=request.user)

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")

        assignment = Assignment.objects.create(
            created_by=teacher,
            title=title,
            description=description
        )

        return redirect("teacher_assignment_detail", assignment_id=assignment.id)

    return render(request, "create_assignment.html")

@login_required
@teacher_required
def teacher_assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, created_by__user=request.user)
    assigned_classes = assignment.assigned_classes.select_related("for_class")

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
    submissions = StudentSubmission.objects.filter(assignment=assigned.assignment).select_related('student__user')

    return render(request, "teacher_view_submissions.html", {
        "assigned": assigned,
        "submissions": submissions,
    })


@login_required
@student_required
def submit_assignment(request, assigned_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    assigned = get_object_or_404(AssignedToClass, id=assigned_id)
    student = request.user.student

    if assigned.for_class not in student.classes.all():
        return HttpResponse("Access denied", status=403)

    submission, _ = StudentSubmission.objects.get_or_create(
        student=student,
        assignment=assigned.assignment,
    )

    if submission.submitted:
        return JsonResponse({"error": "Already submitted"}, status=400)

    try:
        data = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    code = data.get("code", "").strip()
    filename = data.get("name", "assignment.py")

    if not code:
        return JsonResponse({"error": "No code submitted"}, status=400)

    if not filename.lower().endswith(".py"):
        filename += ".py"

    label = slugify(filename[:-3]) or "assignment"
    path = (
        f"class-{assigned.for_class.id}/"
        f"student-{student.id}/"
        f"assignment-{assigned.id}/"
        f"{label}.py"
    )

    upload = submission.upload or Uploads.objects.create(
        person=student.user,
        for_class=assigned.for_class,
        display_name=filename,
    )

    upload.file.save(path, ContentFile(code), save=True)

    submission.upload = upload
    submission.submitted = True
    submission.save()

    return JsonResponse({"ok": True})

@login_required
@teacher_required
def create_homework_template(request):

    if request.method == 'POST':
        template_form = HomeworkTemplateForm(request.POST)
        formset = HomeworkQuestionFormSet(request.POST or None, queryset=HomeworkQuestion.objects.none(), prefix='form')
        if template_form.is_valid() and formset.is_valid():
            template = template_form.save()

            for question_form in formset:
                if question_form.cleaned_data and not question_form.cleaned_data.get('DELETE', False):
                    question = question_form.save(commit = False)
                    question.template = template
                    question.save()

                    if question.question_type == 'multiple_choice':
                        choice_formset = HomeworkChoiceFormSet(request.POST, prefix = f'choices_{question_form.prefix}', instance = question)
                        if choice_formset.is_valid():
                            choice_formset.save()
            return redirect('teacher_dashboard')
    else:
        template_form = HomeworkTemplateForm()
        formset = HomeworkQuestionFormSet(queryset=HomeworkQuestion.objects.none(), prefix='form')

    choice_formsets = []
    for i, question_form in enumerate(formset.forms):
        prefix = f'choices_form-{i}'
        choice_formset = HomeworkChoiceFormSet(prefix=prefix)
        choice_formsets.append(choice_formset)

    formset_with_choices = zip(formset.forms, choice_formsets)
    empty_question_form = formset.empty_form
    teacher = Teacher.objects.get(user = request.user)

    return render(request, 'create_homework_template.html', {
        'template_form': template_form,
        'formset': formset,
        'formset_with_choices': formset_with_choices,
        'empty_question_form': empty_question_form,
        'teacher': teacher
    })

@login_required
@student_required
def student_form_view(request, assigned_hw_id):
    assigned = get_object_or_404(AssignedHomework, id=assigned_hw_id)
    my_form = assigned.template
    questions = list(my_form.questions.all())
    
    completed = StudentQuestionResponse.objects.filter(student = request.user.student, assigned_homework = assigned).exists()
    if completed:
        return redirect ('student_assignments')
    
    initial_data = [{'question': question} for question in questions]

    StudentAnswerFormSet = modelformset_factory(
        StudentQuestionResponse,
        form=StudentAnswerForm,
        extra=len(initial_data)
    )
    
    if request.method == 'POST':

        formset = StudentAnswerFormSet(request.POST, request.FILES, queryset = StudentQuestionResponse.objects.none())
        
        for form, question in zip(formset.forms, questions):
            form.fields['selected_choice'].queryset = question.choices.all()
            
        if formset.is_valid():
            for form, question in zip(formset.forms, questions):
                form.instance.student = request.user.student
                form.instance.question = question
                form.instance.assigned_homework = assigned

                if getattr(question, 'question_type', None) == 'file':

                    code = request.POST.get(f'code_q{question.id}', '') or ''
                    if code.strip():
                        display_name = f"{assigned.template.name}-q{question.id}"
                        label = slugify(display_name) or f"q{question.id}"
                        # Organize by class / student / assignment
                        filename = f"class-{assigned.for_class_id}/student-{request.user.id}/assigned-{assigned.id}/{label}.py"

                        upload = Uploads(
                            person=request.user,
                            for_class=assigned.for_class,
                            display_name=display_name
                        )
                        upload.file.save(filename, ContentFile(code), save=True)
                        form.instance.upload = upload
                    else:
                        form.instance.upload = None

                uploaded_file = form.cleaned_data.get('upload')
                
                if uploaded_file:
                    upload = Uploads.objects.create(
                    file=uploaded_file,
                    person=request.user,
                    for_class=assigned.for_class,
                )
                    form.instance.upload = upload
                form.instance.save()

            return redirect('student_dashboard')
        else:
                for i, form in enumerate(formset.forms):
                    print(f"Form {i} valid: {form.is_valid()}")
                    print("Errors:", form.errors)
        
    else:
        formset = StudentAnswerFormSet(queryset=StudentQuestionResponse.objects.none(), initial = initial_data)
    
    responses = StudentQuestionResponse.objects.filter(student = request.user.student, assigned_homework = assigned)
    initial_code_map = {}
    for r in responses:
        if r.upload and r.upload.file:
            try:
                r.upload.file.open("rb")
                text = r.upload.file.read().decode("utf-8")
            except:
                text = ""
            initial_code_map[r.question.id] = text
        else:
            initial_code_map[r.question.id] = ""
    return render(request, 'student_form_view.html', {'assigned':assigned, 'formset':formset, 'student_id':request.user.student.id, 'initial_code_map': initial_code_map})

@login_required
@teacher_required
def responses_view(request, assigned_hw_id):
    assigned = get_object_or_404(AssignedHomework, id = assigned_hw_id)
    template = assigned.template
    questions = template.questions.all()
    teacher = Teacher.objects.get(user = request.user)
    submission_count = (
        StudentQuestionResponse.objects
        .filter(assigned_homework=assigned)
        .values('student')
        .distinct()
        .count()
    )
    question_data = []

    for question in questions:
        responses = StudentQuestionResponse.objects.filter(
            question = question, 
            assigned_homework = assigned
        )
        question_data.append({
            'question':question, 
            'responses':responses
        })

    return render(request, 'responses_view.html', {'assigned':assigned, 'question_data' : question_data, 'submission_count':submission_count, 'teacher':teacher})

@login_required
@student_required
def student_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code)
    student = request.user.student
    
    if class_obj not in student.classes.all():
        return redirect('student_dashboard')
    
    """
    assigned_homework = AssignedHomework.objects.filter(for_class = class_obj).select_related('template')
    weekly_assignments = defaultdict(lambda: {'assignments': []})

    for hw in assigned_homework:
        week = hw.template.class_week
        weekly_assignments[week]['assignments'].append(hw)
    sorted_weeks = dict(sorted(weekly_assignments.items()))
    context = {
        'class': class_obj,
        'sorted_weeks': sorted_weeks,
    }
    """
    assigned_assignments = AssignedToClass.objects.filter(for_class = class_obj).select_related('assignment').order_by('due_date')
    return render(request, 'student_class_view.html', {
        'class': class_obj,
        'assigned_assignments': assigned_assignments
    })

    #return render(request, 'student_class_view.html', context)

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
    """
    curriculum = class_obj.curriculum
    homework_templates = HomeworkTemplate.objects.filter(curriculum_id = curriculum.id)
    assigned_homeworks = AssignedHomework.objects.filter(for_class = class_obj)
    teacher = Teacher.objects.get(user = request.user)

    return render(request, 'teacher_class_view.html', {
        'class': class_obj,
        'homework_templates': homework_templates,
        'assigned_homeworks': assigned_homeworks,
        'students': students,
        'teacher': teacher,
    })
    """

@csrf_exempt
def get_code_feedback(request):
    
    if request.method == 'POST':
        try:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)

            code = data.get("code")
            question_id = int(data.get("question_id"))
            student_id = int(data.get("student_id"))

            if not code or not question_id:
                return JsonResponse({"error": "Missing code or question_id"}, status=400)

            feedback = get_ai_review(request, code, question_id)

            AIFeedback.objects.create(
                question = get_object_or_404(HomeworkQuestion, id=question_id),
                student = get_object_or_404(Student, id = student_id),
                response=feedback,
            )
            
            if not feedback:
                return JsonResponse({"error": "AI returned no feedback."}, status = 400)
            print("AI results", feedback)
            return JsonResponse({"feedback": feedback})
        except Exception as e:
            tb = traceback.format_exc()
            return JsonResponse({"error": str(e), "traceback": tb}, status=400)
        
def get_due_date_form(request, class_id, template_id):
    form = AssignHomeworkDueDateForm(initial={'class_id': class_id, 'template_id': template_id})
    return render (request, 'due_date_form.html', {'form': form})

def assign_homework_assignment(request):
    if request.method == 'POST':
        form = AssignHomeworkDueDateForm(request.POST)
        if form.is_valid():
            class_id = form.cleaned_data['class_id']
            template_id = form.cleaned_data['template_id']
            due_date = form.cleaned_data['due_date']

            class_obj = get_object_or_404(Class, id=class_id, teacher = request.user.teacher)
            template = get_object_or_404(HomeworkTemplate, id=template_id, curriculum = class_obj.curriculum)

            if not class_obj or not template:
                return HttpResponseBadRequest("Invalid class or template.")

            AssignedHomework.objects.create(
                for_class=class_obj,
                template=template,
                due_date=due_date
            )

            return HttpResponse("Assigned")
        else:
            return render(request, 'partials/due_date_form.html', {'form': form, 'teacher' : request.user.teacher})
    return HttpResponseBadRequest("Invalid request.")

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

    if assigned and hasattr(user, "student"):
        upload = Uploads.objects.filter (
            person=user,
            assignment=assigned.assignment
        ).first()

        if upload and upload.file:
            try:
                upload.file.open("rb")
                initial_code = upload.file.read().decode("utf-8")
                code_name = upload.display_name
                selected_class_id = str(assigned.for_class.id)
            except Exception:
                pass

    # JSON AUTOSAVE (editor autosave)
    if request.method == "POST" and is_json:
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

        code = data.get("code", "")
        name = data.get("name", "code.py")

        class_id = data.get("class_id")

        if not name.lower().endswith(".py"):
            name += ".py"

        # ASSIGNMENT AUTOSAVE
        if assigned and hasattr(user, "student"):
            upload, _ = Uploads.objects.get_or_create(
                person=user,
                assignment=assigned.assignment,
                defaults={
                    "for_class": assigned.for_class,
                    "display_name": assigned.assignment.title,
                },
            )
            upload.display_name = assigned.assignment.title

            upload.file.save(
                upload.display_name or "code.py",
                ContentFile(code),
                save=True,
            )

            return JsonResponse({"ok": True, "autosaved": True})
        # CLASSWORK AUTOSAVE
        if not class_id:
            return JsonResponse(
                {"ok": False, "error": "Missing class_id"},
                status=400,
            )

        class_obj = get_object_or_404(Class, id=class_id)

        upload, _ = Uploads.objects.get_or_create(
            person=user,
            for_class=class_obj,
            display_name=name,
        )

        label = slugify(name[:-3]) or "code"
        upload.file.save(name, ContentFile(code), save=True)

        return JsonResponse({"ok": True, "autosaved": True})


    # Load file by upload_id (editor)
    upload_id = request.GET.get("upload_id")

    if upload_id and not assigned:
        upload = get_object_or_404(Uploads, id=upload_id)

        if not (
            upload.person == user
            or (hasattr(user, "teacher") and upload.for_class and upload.for_class.teacher == user.teacher)
            or user.is_superuser
        ):
            return HttpResponse("Access denied", status=403)

        selected_class_id = str(upload.for_class.id)
        upload.file.open("rb")
        initial_code = force_str(upload.file.read(), errors="ignore")
        code_name = upload.display_name or upload.file.name.split("/")[-1]
        selected_class_id = str(upload.for_class.id)

    # Class dropdown options
    if hasattr(user, "teacher"):
        class_options = user.teacher.classes.all()
    elif hasattr(user, "student"):
        class_options = user.student.classes.all()
    else:
        class_options = []

    files_by_class = defaultdict(list)

    uploads = (
        Uploads.objects
            .filter(person=request.user)
            .select_related("for_class", "assignment")
            .order_by("-last_edited")
    )

    assigned_lookup = {}  # (can remove entirely if unused)

    for upload in uploads:
        # attach assigned_id for template use
        upload.assigned_id = (
            assigned_lookup.get(upload.assignment_id)
            if upload.assignment_id
            else None
        )

        if upload.for_class:
            files_by_class[upload.for_class].append(upload)


    return render(request, "editor_view.html", {
        "user": user,
        "class_options": class_options,
        "initial_code": initial_code,
        "code_name": code_name,
        "selected_class_id": selected_class_id,
        "assigned": assigned,
        "files_by_class": dict(files_by_class),
    })
@login_required
def load_upload(request, pk):
    upload = get_object_or_404(Uploads, pk=pk)

    # Security
    if not (
        upload.person == request.user
        or (hasattr(request.user, "teacher")
            and upload.for_class
            and upload.for_class.teacher == request.user.teacher)
        or request.user.is_superuser
    ):
        return JsonResponse({"ok": False}, status=403)

    upload.file.open("rb")
    code = force_str(upload.file.read(), errors="ignore")

    return JsonResponse({
        "ok": True,
        "code": code,
        "name": upload.display_name,
        "class_id": upload.for_class_id,
    })
