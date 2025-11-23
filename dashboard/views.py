from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from .forms import HomeworkUpload, ClassworkUpload, HomeworkTemplateForm, HomeworkQuestionFormSet, HomeworkChoiceFormSet, StudentAnswerForm, StudentCreationForm, TeacherCreationForm, CurriculumCreationForm, ClassCreationForm, ClassStudentUpdateForm, StudentPasswordResetForm, TeacherPasswordResetForm, AssignHomeworkDueDateForm, MaterialForm
from .models import Student, Uploads, Teacher, User, Class, HomeworkQuestion, AssignedHomework, StudentQuestionResponse, HomeworkTemplate, Material, PostedMaterial, AIFeedback
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

    hw_files = user.uploads_set.filter(file_type = 'HW').order_by("-uploaded_at")
    cw_files = user.uploads_set.filter(file_type = 'CW').order_by("-uploaded_at")

    hw_form = HomeworkUpload()
    cw_form = ClassworkUpload()

    
    if request.method == 'POST':
        if 'upload_hw' in request.POST:

            hw_form = HomeworkUpload(request.POST, request.FILES)
            if hw_form.is_valid():
                hw_form.save(user = user)
                return redirect('student_dashboard')
        
        elif 'upload_cw' in request.POST:
            cw_form = ClassworkUpload(request.POST, request.FILES)
            if cw_form.is_valid():
                cw_form.save(user = user)
                return redirect('student_dashboard')
    
    classes = []
    
    for section in student.classes.all():
        hw_form = HomeworkUpload(initial={'for_class': section})
        cw_form = ClassworkUpload(initial = {'for_class': section})
        hw_files = student.user.uploads_set.filter(file_type = 'HW').filter(for_class = section).order_by("-uploaded_at")
        cw_files = student.user.uploads_set.filter(file_type = 'CW').filter(for_class = section).order_by("-uploaded_at")

        classes.append({
            'class': section,
            'hw_form': hw_form,
            'cw_form' : cw_form,
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
            last_hw_file = student.latest_file('HW', section)
            
            last_cw_file = student.latest_file('CW', section) 
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
        hw_files = student.user.uploads_set.filter(file_type = 'HW').filter(for_class = section).order_by("-uploaded_at")
        cw_files = student.user.uploads_set.filter(file_type = 'CW').filter(for_class = section).order_by("-uploaded_at")

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
def download_material_view(request, material_id):
    try:
        material = Material.objects.get(id = material_id)
        return FileResponse(
                material.file.open('rb'),
                as_attachment=True,
                filename=material.file.name.split('/')[-1]
        )
    except Material.DoesNotExist:
        raise Http404("Material not found")

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
                            file_type='HW',
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
                    file_type = 'HW',
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
    
    assigned_homework = AssignedHomework.objects.filter(for_class = class_obj).select_related('template')
    posted_material = PostedMaterial.objects.filter(for_class = class_obj).select_related('material')
    weekly_assignments = defaultdict(lambda: {'assignments': [], 'materials': []})

    for hw in assigned_homework:
        week = hw.template.class_week
        weekly_assignments[week]['assignments'].append(hw)
    for pm in posted_material:
        week = pm.material.class_week
        weekly_assignments[week]['materials'].append(pm.material)
    general_materials = weekly_assignments.pop(0, {'assignments': [], 'materials': []})
    sorted_weeks = dict(sorted(weekly_assignments.items()))
    context = {
        'class': class_obj,
        'general_materials': general_materials,
        'sorted_weeks': sorted_weeks,
    }

    return render(request, 'student_class_view.html', context)

@login_required
@teacher_required
def teacher_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code, teacher = request.user.teacher)
    curriculum = class_obj.curriculum
    homework_templates = HomeworkTemplate.objects.filter(curriculum_id = curriculum.id)
    curriculum_materials = Material.objects.filter(curriculum = curriculum)
    assigned_homeworks = AssignedHomework.objects.filter(for_class = class_obj)
    teacher = Teacher.objects.get(user = request.user)

    students = class_obj.students.all()

    return render(request, 'teacher_class_view.html', {
        'class': class_obj,
        'homework_templates': homework_templates,
        'curriculum_materials': curriculum_materials,
        'assigned_homeworks': assigned_homeworks,
        'students': students,
        'teacher': teacher,
    })

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

@csrf_exempt
def post_material(request, class_id, material_id):
    if request.method == "POST":
        class_obj = Class.objects.get(id=class_id, teacher=request.user.teacher)
        material = Material.objects.get(id=material_id, curriculum=class_obj.curriculum)
        if not class_obj or not material:
            return HttpResponseBadRequest("Invalid class or material.")

        if not PostedMaterial.objects.filter(for_class=class_obj, material=material).exists():
            PostedMaterial.objects.create(for_class=class_obj, material=material)
            
        return HttpResponse("Material posted.")

def create_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save()
            return redirect('admin_dashboard')
    else:
        form = MaterialForm()

    return render(request, 'create_material.html', {'form': form, 'teacher': request.user.teacher})

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
    #assigned_homework = get_object_or_404(AssignedHomework, id=homework_id)
    #question = get_object_or_404(HomeworkQuestion, id=question_id, assigned_homework=assigned_homework)
    
    user = request.user

    if request.method == "POST" and request.headers.get("content-type", "").startswith("application/json"):
            import json
            try:
                data = json.loads(request.body)
            except Exception:
                return HttpResponseBadRequest("Invalid JSON")

            code = data.get("code", "")
            name = data.get("name", "untitled")
            class_id = data.get("class_id")
            if name.lower().endswith(".py"):
                base_name = name[:-3]
            else:
                base_name = name
            name = base_name + ".py"
            class_id = data.get("class_id")

            class_obj = get_object_or_404(Class, id=class_id)

            upload, _ = Uploads.objects.get_or_create(
                person=user,
                for_class=class_obj,
                display_name=name,
                file_type="CW",
            )

            label = slugify(name[:-3]) or "code"
            filename = f"{class_id}/user-{request.user.id}/{label}.py"
            upload.file.save(filename, ContentFile(code), save=True)

            return JsonResponse({
                "ok": True,
                "file_id": upload.id,
                "display_name": name[:-3],
                "filename": filename,
                "class": class_obj.name,
            })
    elif request.method == "POST":
        if request.headers.get("x-requested-with") != "XMLHttpRequest":
            return HttpResponseBadRequest("Invalid AJAX request.")
           
        code = request.POST.get("code", "")
        name = request.POST.get("name", "untitled")+".py"
        class_id = request.POST.get("class_id")
        class_obj = get_object_or_404(Class, id=class_id)

        upload, _ = Uploads.objects.get_or_create(
            person=request.user,
            for_class=class_obj,
            display_name = name,
            file_type = "CW",
        )

        name = name[:-3]
        label = slugify(name) or "code"
        filename = f"{class_id}/user-{request.user.id}/{label}.py"
        upload.file.save(filename, ContentFile(code), save=True)

        return JsonResponse({"ok": True, "file_id": upload.id, "display_name": name, "filename":filename, "class": class_obj.name})
    
    upload_id = request.GET.get("upload_id")

    initial_code = ""
    code_name = ""
    selected_class_id = None

    if upload_id:
        u = get_object_or_404(Uploads, id=upload_id)

        if not (u.person == user or (hasattr(user, "teacher") and u.for_class and u.for_class.teacher == user.teacher) or user.is_superuser):
            return HttpResponse("Access denied.", status=403)
        selected_class_id = str(u.for_class.id)
        u.file.open("rb")
        data = u.file.read()
        initial_code = force_str(data, errors="ignore")
        code_name = u.display_name or u.file.name.split("/")[-1]



    if hasattr(user, "teacher"):
        class_options = user.teacher.classes.all()
    elif hasattr(user, "student"):
        class_options = user.student.classes.all()
    else:
        class_options = []
    
    
    return render(request, "editor_view.html", {"user": request.user, "class_options": class_options, "initial_code": initial_code, "code_name": code_name, "selected_class_id": selected_class_id})

@csrf_exempt
@login_required
def mini_autosave_view(request):
    """
    Autosaves code typed into a mini editor for a specific homework question.
    It updates or creates a StudentQuestionResponse for that question + student.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    try:
        data = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    code = data.get("code", "").strip()
    qid = data.get("question_id")
    class_id = data.get("class_id")
    name = data.get("name", "mini_autosave.py")

    # Basic validation
    if not (qid and class_id and request.user.is_authenticated):
        return JsonResponse({"error": "Missing data"}, status=400)

    # Get the question
    try:
        question = HomeworkQuestion.objects.get(id=qid)
    except HomeworkQuestion.DoesNotExist:
        return JsonResponse({"error": "Question not found"}, status=404)

    # Get the student's class and assigned homework
    student = request.user.student
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return JsonResponse({"error": "Class not found"}, status=404)

    # Find the AssignedHomework for this class and this question’s template
    assigned = AssignedHomework.objects.filter(
        for_class=class_obj,
        template=question.template
    ).first()

    if not assigned:
        return JsonResponse({"error": "AssignedHomework not found"}, status=404)
    
    if not name.lower().endswith(".py"):
        name += ".py"

    from django.core.files.base import ContentFile
    label = slugify(name[:-3]) or f"q{qid}"
    filepath = f"class-{class_id}/student-{student.id}/question-{qid}/{label}.py"

    upload, _ = Uploads.objects.get_or_create(
        person=request.user,
        for_class=class_obj,
        display_name=name,
        file_type="HW",
    )

    upload.file.save(filepath, ContentFile(code), save=True)

    # Save or update student's response
    response_obj, created = StudentQuestionResponse.objects.update_or_create(
        student=student,
        assigned_homework=assigned,
        question=question,
        defaults={"upload": upload},
    )

    return JsonResponse({
        "ok": True,
        "upload_id": upload.id,
        "filename": filepath,
        "display_name": name,
    })