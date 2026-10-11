"""
Django management command to set up test data for load testing.
Run with: LOAD_TEST_PASSWORD=... python manage.py setup_load_test
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from dashboard.models import Student, Teacher, Class, Curriculum, Assignment, AssignedToClass, CodeProject, ProjectFile
from django.utils import timezone
from django.core.files.base import ContentFile


class Command(BaseCommand):
    help = 'Set up test data for load testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-students',
            type=int,
            default=10,
            help='Number of test students to create'
        )
        parser.add_argument(
            '--num-classes',
            type=int,
            default=2,
            help='Number of test classes to create'
        )

    def handle(self, *args, **options):
        num_students = options['num_students']
        num_classes = options['num_classes']

        password = os.environ.get('LOAD_TEST_PASSWORD')
        if not password:
            raise CommandError("Set the LOAD_TEST_PASSWORD environment variable before running this command.")

        self.stdout.write("Setting up load test data...")

        # Create or get test teacher
        teacher_user, created = User.objects.get_or_create(
            username='loadtest_teacher1',
            defaults={
                'first_name': 'Load',
                'last_name': 'Test Teacher',
                'email': 'loadtest_teacher@example.com'
            }
        )
        if created:
            teacher_user.set_password(password)
            teacher_user.save()
            self.stdout.write(f"Created teacher user: {teacher_user.username}")

        teacher, _ = Teacher.objects.get_or_create(user=teacher_user)
        teacher.is_admin = True
        teacher.save()

        # Create test curriculum
        curriculum, _ = Curriculum.objects.get_or_create(
            name='Load Test Curriculum'
        )
        self.stdout.write(f"Created curriculum: {curriculum.name}")

        # Create test classes
        classes = []
        for i in range(num_classes):
            class_obj, _ = Class.objects.get_or_create(
                name=f'Load Test Class {i+1}',
                teacher=teacher,
                defaults={
                    'curriculum': curriculum,
                    'day': 'All Week',
                    'location': 'Online'
                }
            )
            classes.append(class_obj)
            self.stdout.write(f"Created class: {class_obj.name} (code: {class_obj.code})")

        # Create test assignments
        assignments = []
        for i in range(2):
            assignment, created = Assignment.objects.get_or_create(
                title=f'Load Test Assignment {i+1}',
                defaults={
                    'curriculum': curriculum,
                    'created_by': teacher,
                    'description': f'Test assignment {i+1}'
                }
            )
            assignments.append(assignment)

            # Assign to all test classes
            for class_obj in classes:
                AssignedToClass.objects.get_or_create(
                    assignment=assignment,
                    for_class=class_obj,
                    defaults={'due_date': timezone.now() + timezone.timedelta(days=30)}
                )

            self.stdout.write(f"Created assignment: {assignment.title}")

        # Create test students and enroll them in classes
        for i in range(num_students):
            student_user, created = User.objects.get_or_create(
                username=f'loadtest_student{i+1}',
                defaults={
                    'first_name': f'Student{i+1}',
                    'last_name': 'LoadTest',
                    'email': f'loadtest_student{i+1}@example.com'
                }
            )
            if created:
                student_user.set_password(password)
                student_user.save()

            student, _ = Student.objects.get_or_create(user=student_user)

            # Enroll in all test classes
            for class_obj in classes:
                student.classes.add(class_obj)

            if created:
                self.stdout.write(f"Created student: {student_user.username}")

        # Create sample projects and files for each student/assignment/class combo
        for class_obj in classes:
            for assignment in assignments:
                for i in range(num_students):
                    student_user = User.objects.get(username=f'loadtest_student{i+1}')

                    project, created = CodeProject.objects.get_or_create(
                        owner=student_user,
                        for_class=class_obj,
                        assignment=assignment,
                        defaults={'submitted': False}
                    )

                    if created:
                        # Create initial main.py file
                        main_file = ProjectFile(
                            project=project,
                            path='main.py'
                        )
                        main_file.file.save(
                            'main.py',
                            ContentFile(b'print("Hello, World!")'),
                            save=True
                        )
                        self.stdout.write(
                            f"Created project for {student_user.username} "
                            f"in {class_obj.name} for {assignment.title}"
                        )

        self.stdout.write(self.style.SUCCESS("Load test data setup complete!"))
        self.stdout.write("")
        self.stdout.write("Test Credentials:")
        self.stdout.write(f"  Teacher: loadtest_teacher1 (password from LOAD_TEST_PASSWORD)")
        self.stdout.write(f"  Students: loadtest_student1..{num_students} (password from LOAD_TEST_PASSWORD)")
        self.stdout.write(f"  Total: {num_students} students in {num_classes} classes with {len(assignments)} assignments each")
