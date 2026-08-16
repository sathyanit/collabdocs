from django.contrib import admin
from .models import Document, DocumentVersion, DocumentCollaborator


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'workspace', 'status', 'created_by', 'is_pinned', 'created_at', 'updated_at')
    list_filter = ('status', 'is_pinned', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'workspace__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace', 'parent', 'created_by', 'last_edited_by')


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version_number', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('document__title',)
    readonly_fields = ('version_number', 'created_at')
    raw_id_fields = ('document', 'created_by')


@admin.register(DocumentCollaborator)
class DocumentCollaboratorAdmin(admin.ModelAdmin):
    list_display = ('document', 'user', 'can_edit', 'added_at')
    list_filter = ('can_edit', 'added_at')
    search_fields = ('document__title', 'user__email')
    raw_id_fields = ('document', 'user', 'added_by')
