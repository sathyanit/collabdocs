from django.contrib import admin
from .models import Workspace, WorkspaceMember, Invitation


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'owner__email', 'owner__first_name', 'owner__last_name')
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('owner',)


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'user', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('workspace__name', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('id', 'joined_at')
    raw_id_fields = ('workspace', 'user', 'invited_by')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'workspace', 'role', 'inviter', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'role', 'created_at', 'expires_at')
    search_fields = ('email', 'workspace__name', 'inviter__email')
    readonly_fields = ('id', 'token', 'created_at', 'accepted_at')
    raw_id_fields = ('workspace', 'inviter')
