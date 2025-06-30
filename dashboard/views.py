from django.shortcuts import render
from django.http import FileResponse, Http404
from .forms import StudentFileForm
from .models import Student, StudentFile
from django.contrib.auth.decorators import login_required

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
