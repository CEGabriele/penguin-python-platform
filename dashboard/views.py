from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from .forms import HomeworkUpload, ClassworkUpload, AssignmentForm, AssignmentUpload, HomeworkFormForm, HomeworkQuestionFormSet, HomeworkChoiceFormSet, StudentAnswerForm, StudentCreationForm, TeacherCreationForm
from .models import Student, Uploads, Teacher, User, Class, Assignment, HomeworkQuestion, HomeworkForm, StudentQuestionResponse
from django.contrib.auth.decorators import login_required
from itertools import groupby
from operator import attrgetter
from django.forms import modelformset_factory
from django.views.decorators.csrf import csrf_exempt
import json
import traceback

from dashboard.services.ai_hw_review import get_ai_review

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
    if request.user.teacher.is_admin:
        
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
        
        
        
        return render(request, 'admin_dashboard.html', {'student_form':student_form, 'teacher_form':teacher_form} )
    else:
        return redirect('login')


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
    return render(request, 'view_student.html', {'student': student, 'teacher': teacher, 'student_files': student_files})


@login_required
def download_file_view(request, file_id):
    try:
        file = Uploads.objects.get(id = file_id)
        return FileResponse(
            file.file.open('rb'),
            as_attachment=True,
            filename = file.file.name.split('/')[-1]
        )
    except Uploads.DoesNotExist:
        raise Http404("File not found or access denied")


@login_required
@teacher_required
def create_assignment(request):
    teacher = Teacher.objects.get(user  = request.user)
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save()
        return redirect('teacher_dashboard')
    else:
        form = AssignmentForm(teacher = teacher)

        
    return render(request, 'create_assignment.html', {'form': form})


@login_required
@student_required
def student_assignments(request):
    student = Student.objects.get(user = request.user)
    classes = student.classes.all()
    assignments = Assignment.objects.filter(for_class__in = classes).order_by('for_class__name', 'due_date')
    forms = HomeworkForm.objects.filter(for_class__in = classes).order_by('for_class__name', 'due_date')

    class_assignments = {class_obj: list(grouped_assignments)
                         for class_obj, grouped_assignments in groupby(assignments, key = attrgetter('for_class'))}
    
    class_forms = {class_obj: list(grouped_assignments)
                   for class_obj, grouped_assignments in groupby(forms, key = attrgetter('for_class'))

    }

    return render(request, 'student_assignments.html', {'class_forms':class_forms})


@login_required
@teacher_required
def teacher_assignments_list(request):
    teacher = Teacher.objects.get(user = request.user)
    classes = teacher.classes.all()
    assignments = Assignment.objects.filter(for_class__in = classes).order_by('for_class__name', 'due_date')
    forms = HomeworkForm.objects.filter(for_class__in = classes).order_by('for_class__name', 'due_date')

    class_assignments = {class_obj: list(grouped_assignments)
                         for class_obj, grouped_assignments in groupby(assignments, key = attrgetter('for_class'))}
    
    
    class_forms = {class_obj: list(grouped_assignments)
                   for class_obj, grouped_assignments in groupby(forms, key = attrgetter('for_class'))
    }

    return render(request, 'teacher_assignments_list.html', {'class_forms':class_forms})

@login_required
@student_required
def student_assignment_view(request, assignment_id):
    student = request.user.student
    assignment = get_object_or_404(Assignment, id=assignment_id, for_class__in = student.classes.all())

    
    form = AssignmentUpload()

    if request.method == 'POST':
        form = AssignmentUpload(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit = False)
            upload.for_assignment = assignment
            upload.for_class = assignment.for_class
            upload.person = request.user
            upload.file_type = 'HW'
            upload.save()
            return redirect('assignment_details', assignment_id = assignment.id)

    uploaded_files = Uploads.objects.filter(
        person = request.user,
        for_assignment = assignment
    ).order_by('-uploaded_at')

    return render(request, 'student_assignment_view.html', {
        'assignment': assignment,
        'uploaded_files': uploaded_files,
        'form': form
    })

@login_required
@teacher_required
def teacher_assignment_detail(request, assignment_id):
    teacher = request.user.teacher
    assignment = get_object_or_404(Assignment, id=assignment_id, for_class__teacher=teacher)
    students = Student.objects.filter(classes=assignment.for_class).distinct()

    student_submissions = []
    
    for student in students:
        files = Uploads.objects.filter(person=student.user, for_assignment=assignment).order_by('-uploaded_at')
        student_submissions.append((student, files))

    return render(request, 'teacher_assignment_detail.html', {
        'assignment': assignment,
        'student_submissions': student_submissions,
    })

@login_required
@teacher_required
def create_homework_form(request):

    teacher = request.user.teacher

    if request.method == 'POST':
        assignment_form = HomeworkFormForm(request.POST)
        formset = HomeworkQuestionFormSet(request.POST or None, queryset=HomeworkQuestion.objects.none(), prefix='form')
        if assignment_form.is_valid() and formset.is_valid():
            assignment = assignment_form.save()

            for question_form in formset:
                if question_form.cleaned_data and not question_form.cleaned_data.get('DELETE', False):
                    question = question_form.save(commit = False)
                    question.form = assignment
                    question.save()

                    if question.question_type == 'multiple_choice':
                        choice_formset = HomeworkChoiceFormSet(request.POST, prefix = f'choices_{question_form.prefix}', instance = question)
                        if choice_formset.is_valid():
                            choice_formset.save()
            return redirect('teacher_dashboard')
    else:
        assignment_form = HomeworkFormForm()
        formset = HomeworkQuestionFormSet(queryset=HomeworkQuestion.objects.none(), prefix='form')

    choice_formsets = []
    for i, question_form in enumerate(formset.forms):
        prefix = f'choices_form-{i}'
        choice_formset = HomeworkChoiceFormSet(prefix=prefix)
        choice_formsets.append(choice_formset)

    formset_with_choices = zip(formset.forms, choice_formsets)
    empty_question_form = formset.empty_form

    return render(request, 'create_homework_form.html', {
        'assignment_form': assignment_form,
        'formset': formset,
        'formset_with_choices': formset_with_choices,
        'empty_question_form': empty_question_form,
    })

@login_required
@student_required
def student_form_view(request, form_id):
    my_form = HomeworkForm.objects.get(id = form_id)
    questions = list(my_form.questions.all())
    
    
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
                
                
                uploaded_file = form.cleaned_data.get('upload')
                
                if uploaded_file:
                    upload = Uploads.objects.create(
                    file=uploaded_file,
                    person=request.user,
                    file_type = 'HW',
                    for_class=my_form.for_class,
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

    return render(request, 'student_form_view.html', {'my_form':my_form, 'formset':formset})

@login_required
@teacher_required
def responses_view(request, form_id):
    form = get_object_or_404(HomeworkForm, id = form_id)
    questions = form.questions.all()

    question_data = []

    for question in questions:
        responses = StudentQuestionResponse.objects.filter(question = question)
        question_data.append({'question':question, 'responses':responses})

    return render(request, 'responses_view.html', {'form':form, 'question_data' : question_data})

@login_required
@student_required
def student_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code)
    student = request.user.student
    if class_obj not in student.classes.all():
        return redirect('student_dashboard')
    return render(request, 'student_class_view.html', {
        'class': class_obj
    })

@login_required
@teacher_required
def teacher_class_view(request, class_code):
    class_obj = get_object_or_404(Class, code=class_code)
    teacher = request.user.teacher
    if teacher != class_obj.teacher:
        return redirect('teacher_dashboard')
    return render(request, 'teacher_class_view.html', {
        'class': class_obj
    })
@csrf_exempt
def get_code_feedback(request):
    
    if request.method == 'POST':
        try:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)

            code = data.get("code")
            question_id = data.get("question_id")

            if not code or not question_id:
                return JsonResponse({"error": "Missing code or question_id"}, status=400)

            feedback = get_ai_review(code, question_id)
            
            if not feedback:
                return JsonResponse({"error": "AI returned no feedback."}, status = 400)
            print("AI results", feedback)
            return JsonResponse({"feedback": feedback})
        except Exception as e:
            tb = traceback.format_exc()
            return JsonResponse({"error": str(e), "traceback": tb}, status=400)