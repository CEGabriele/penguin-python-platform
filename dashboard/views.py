from django.shortcuts import render
from django.http import FileResponse, Http404
from .forms import StudentFileForm
from .models import Student, StudentFile

def upload_student_file(request):
    student = Student.objects.first() #only works for one user

    if request.method == 'POST':
        form = StudentFileForm(request.POST, request.FILES)
        if form.is_valid():
            student_file = form.save(commit=False)
            student_file.student = student
            student_file.save()
    else:
        form = StudentFileForm()

    return render(request, 'upload_file.html', {'form': form})

def student_file_view(request):
    student = Student.objects.first() #only works for one user
    files = student.studentfile_set.all() 
    return render(request, 'student_files.html', {
        'student': student,
        'files': files
    })

def download_file_view(request, file_id):
    try:
        studentFile = StudentFile.objects.get(id = file_id)
        return FileResponse(
            studentFile.file.open('rb'),
            as_attachment=True,
            filename = studentFile.file.name.split('/')[-1]
        )
    except StudentFile.DoesNotExist:
        raise Http404("File not found")
