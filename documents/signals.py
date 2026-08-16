from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Document, AuditLog


@receiver(pre_save, sender=Document)
def document_pre_save(sender, instance, **kwargs):
    instance._is_adding = instance._state.adding


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    is_created = getattr(instance, '_is_adding', created)
    action = 'created' if is_created else 'updated'
    actor = instance.created_by if is_created else (instance.last_edited_by or instance.created_by)
    AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name='Document',
        object_id=str(instance.id)
    )
