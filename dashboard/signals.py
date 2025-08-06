from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AssignedHomework, StudentQuestionResponse, HomeworkQuestion, HomeworkTemplate, CompletedCurriculum

@receiver(post_save, sender=AssignedHomework)
def update_completed_curriculum(sender, instance, created, **kwargs):
    if created:
        
        assigned = instance
        template = assigned.template
        week = getattr(template, 'class_week', None)
        curriculum = template.curriculum
        for_class = assigned.for_class

        for student in for_class.students.all():
            progress, created = CompletedCurriculum.objects.get_or_create(
            student=student,
            curriculum=curriculum,
            defaults={
                'completed_weeks': week,
            }
        )

        if not created and week > progress.completed_weeks:
            progress.completed_weeks = week
            progress.save()