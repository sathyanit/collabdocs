import uuid
from django.db import models, transaction
from django.db.models import Max
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import json


class DocumentStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    PUBLISHED = 'published', _('Published')
    ARCHIVED = 'archived', _('Archived')


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        db_index=True
    )
    title = models.CharField(max_length=500)
    content = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_documents'
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_documents'
    )
    is_pinned = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', 'order', '-updated_at']
        indexes = [
            models.Index(fields=['workspace', 'parent']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.title

    def get_current_version(self):
        return self.versions.order_by('-version_number').first()


class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    title = models.CharField(max_length=500, blank=True, default='')
    content = models.TextField(blank=True, default='')
    version_number = models.PositiveIntegerField()
    change_summary = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version_number'],
                name='unique_document_version'
            ),
        ]

    def __str__(self):
        return f"{self.document.title} - v{self.version_number}"

    def restore(self, user, save_version=True):
        with transaction.atomic():
            self.document.title = self.title
            self.document.content = self.content
            self.document.last_edited_by = user
            self.document.save()
            if save_version:
                DocumentVersion.objects.create(
                    document=self.document,
                    title=self.title,
                    content=self.content,
                    version_number=self.document.versions.count() + 1,
                    change_summary=f"Restored from version {self.version_number}",
                    created_by=user,
                )
        return self.document


class DocumentCollaborator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    can_edit = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='added_document_collaborators'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'user'],
                name='unique_document_collaborator'
            ),
        ]

    def __str__(self):
        return f"{self.user.email} on {self.document.title}"


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    documents = models.ManyToManyField(
        Document,
        related_name='tags',
        blank=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['actor']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'Anonymous'
        return f"{actor_email} {self.action} {self.model_name} ({self.object_id})"
