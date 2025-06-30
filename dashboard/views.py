from django.shortcuts import render, redirect
from django.http import FileResponse, Http404
from .forms import StudentFileForm
from .models import Student, StudentFile, Teacher
from django.contrib.auth.decorators import login_required

def student_required(view_function):
    def wrapper(request, *args, **kwargs):
        if not Student.objects.filter(user = request.user).exists():
            return redirect('login')
        
        return view_function(request, *args, **kwargs)
    return wrapper

def teacher_required(view_function):
    def wrapper(request, *args, **kwargs):
        if not Teacher.objects.filter(user = request.user).exists():
            return redirect('login')
        
        return view_function(request, *args, **kwargs)
    return wrapper

@login_required
@student_required
def student_dashboard(request):
    student = Student.objects.get(user = request.user) 
    student_files = student.studentfile_set.order_by("-uploaded_at")

    if request.method == 'POST':
        form = StudentFileForm(request.POST, request.FILES)
        if form.is_valid():
            student_file = form.save(commit=False)
            student_file.student = student
            student_file.save()
    else:
        form = StudentFileForm()
    
    
    return render(request, 'student_dashboard.html', {
        'form' : form, 
        'student': student,
        'files': student_files
    })


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

@login_required
def download_file_view(request, file_id):
    try:
        studentFile = StudentFile.objects.get(id = file_id)
        return FileResponse(
            studentFile.file.open('rb'),
            as_attachment=True,
            filename = studentFile.file.name.split('/')[-1]
        )
    except StudentFile.DoesNotExist:
        raise Http404("File not found or student access denied")
