from django.shortcuts import render, redirect
from django.http import FileResponse, Http404
from .forms import HomeworkUpload, ClassworkUpload
from .models import Student, Uploads, Teacher, User
from django.contrib.auth.decorators import login_required

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
    
    student_files = user.uploads_set.order_by("-uploaded_at")
    hw_form = HomeworkUpload()
    cw_form = HomeworkUpload()

    if request.method == 'POST':
        if 'upload_homework' in request.POST:
            hw_form = HomeworkUpload(request.POST, request.FILES)
            if hw_form.is_valid():
                hw_form.save(user = request.user)
                return redirect('student_dashboard')
        elif 'upload_classwork' in request.POST:
            cw_form = HomeworkUpload(request.POST, request.FILES)
            if cw_form.is_valid():
                cw_form.save(user = request.user)
                return redirect('student_dashboard')
    
    
    return render(request, 'student_dashboard.html', {
        'hw_form' : hw_form, 
        'cw_form': cw_form,
        'student': student,
        'files': student_files
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
            last_file = student.latest_file()
            student_info.append({
                'student': student,
                'last_file': last_file
            })

        class_info.append({
            'class': section,
            'students': student_info
        })

            
    return render(request, 'teacher_dashboard.html', {
        'teacher': teacher,
        'classes': class_info
    })

"""

@login_required
def upload_student_file(request):
    student = Student.objects.get(user = request.user) 

    if request.method == 'POST':
        form = StudentFileForm(request.POST, request.FILES)
        if form.is_valid():
            student_file = form.save(commit=False)
            student_file.student = student
            student_file.save()
    else:
        form = StudentFileForm()

    return render(request, 'upload_file.html', {'form': form})


@login_required
def student_file_view(request):
    student = Student.objects.get(user = request.user) 
    student_files = student.studentfile_set.order_by("-uploaded_at")
    
    return render(request, 'student_files.html', {
        'student': student,
        'files': student_files
    })

"""

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
        raise Http404("File not found or student access denied")
