from django.contrib import admin
from .models import Comment, Reaction


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'author', 'is_resolved', 'is_edited', 'created_at', 'updated_at')
    list_filter = ('is_resolved', 'is_edited', 'created_at', 'updated_at')
    search_fields = ('content', 'author__email', 'document__title')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at', 'deleted_at')
    raw_id_fields = ('document', 'author', 'parent', 'resolved_by', 'mentions')


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'reaction_type', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__email',)
    raw_id_fields = ('comment', 'user')
