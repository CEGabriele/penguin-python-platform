from django.shortcuts import render, redirect
from .forms import StudentFileForm
from .models import Student

def upload_student_file(request):
    student = Student.objects.first()

    if request.method == 'POST':
        form = StudentFileForm(request.POST, request.FILES)
        if form.is_valid():
            student_file = form.save(commit=False)
            student_file.student = student  # auto-assign the student
            student_file.save()
    else:
        form = StudentFileForm()

    return render(request, 'upload_file.html', {'form': form})

def student_file_view(request):
    student = Student.objects.first()  # use actual auth later
    files = student.studentfile_set.all()  # uses related_name='files'
    return render(request, 'student_files.html', {
        'student': student,
        'files': files
    })