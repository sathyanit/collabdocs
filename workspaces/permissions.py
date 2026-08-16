from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Workspace, Role, ROLE_PERMISSIONS


class WorkspacePermission(BasePermission):
    permission_required = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Workspace):
            workspace = obj
        elif hasattr(obj, 'workspace'):
            workspace = obj.workspace
        else:
            return False

        if self.permission_required is None:
            return workspace.get_user_role(request.user) is not None

        return workspace.has_permission(request.user, self.permission_required)


class IsWorkspaceOwner(WorkspacePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Workspace):
            workspace = obj
        elif hasattr(obj, 'workspace'):
            workspace = obj.workspace
        else:
            return False
        return request.user == workspace.owner


class IsWorkspaceAdminOrHigher(WorkspacePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Workspace):
            workspace = obj
        elif hasattr(obj, 'workspace'):
            workspace = obj.workspace
        else:
            return False
        role = workspace.get_user_role(request.user)
        return role == Role.ADMIN


class IsWorkspaceEditorOrHigher(WorkspacePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Workspace):
            workspace = obj
        elif hasattr(obj, 'workspace'):
            workspace = obj.workspace
        else:
            return False
        role = workspace.get_user_role(request.user)
        return role in [Role.ADMIN, Role.EDITOR]


class IsWorkspaceMember(WorkspacePermission):
    pass


class CanViewWorkspace(WorkspacePermission):
    permission_required = 'workspace:view'


class CanEditWorkspace(WorkspacePermission):
    permission_required = 'workspace:edit'


class CanDeleteWorkspace(WorkspacePermission):
    permission_required = 'workspace:delete'


class CanInviteToWorkspace(WorkspacePermission):
    permission_required = 'workspace:invite'


class CanManageMembers(WorkspacePermission):
    permission_required = 'workspace:manage_members'


class CanManageRoles(WorkspacePermission):
    permission_required = 'workspace:manage_roles'


class CanCreateDocument(WorkspacePermission):
    permission_required = 'document:create'


class CanViewDocument(WorkspacePermission):
    permission_required = 'document:view'


class CanEditDocument(WorkspacePermission):
    permission_required = 'document:edit'


class CanDeleteDocument(WorkspacePermission):
    permission_required = 'document:delete'


class CanManageVersions(WorkspacePermission):
    permission_required = 'document:manage_versions'


class CanCreateComment(WorkspacePermission):
    permission_required = 'comment:create'


class CanViewComment(WorkspacePermission):
    permission_required = 'comment:view'


class CanEditComment(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author == request.user


class CanDeleteComment(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.author == request.user:
            return True
        if hasattr(obj, 'document') and hasattr(obj.document, 'workspace'):
            workspace = obj.document.workspace
            role = workspace.get_user_role(request.user)
            if role == Role.ADMIN:
                return True
        return False
