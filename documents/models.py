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

    def _resolve_saved_by(self):
        for candidate in [getattr(self, '_saved_by', None), self.last_edited_by, self.created_by]:
            if candidate is not None:
                return candidate
        return None

    def save(self, *args, **kwargs):
        saved_by = self._resolve_saved_by()

        with transaction.atomic():
            super().save(*args, **kwargs)

            version_number = (
                DocumentVersion.objects
                .filter(document=self)
                .aggregate(max_ver=Max('version_number'))
                .get('max_ver') or 0
            ) + 1

            DocumentVersion.objects.create(
                document=self,
                content=self.content,
                version_number=version_number,
                saved_by=saved_by,
            )

        return self

    def set_saved_by(self, user):
        self._saved_by = user
        if self.created_by_id is None:
            self.created_by = user
        self.last_edited_by = user

    def get_current_version(self):
        return self.versions.order_by('-version_number').first()


class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    content = models.TextField(blank=True)
    version_number = models.PositiveIntegerField()
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_versions'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

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
            self.document.content = self.content
            self.document.set_saved_by(user)
            original_flag = getattr(self.document, '_skip_version_on_save', False)
            if not save_version:
                self.document._skip_version_on_save = True
            try:
                self.document.save()
            finally:
                self.document._skip_version_on_save = original_flag
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
