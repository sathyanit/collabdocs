import uuid
from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    ADMIN = 'admin', _('Admin')
    EDITOR = 'editor', _('Editor')
    VIEWER = 'viewer', _('Viewer')


ROLE_PERMISSIONS = {
    Role.ADMIN: [
        'workspace:view',
        'workspace:edit',
        'workspace:delete',
        'workspace:invite',
        'workspace:manage_members',
        'workspace:manage_roles',
        'document:create',
        'document:view',
        'document:edit',
        'document:delete',
        'document:manage_versions',
        'comment:create',
        'comment:view',
        'comment:edit',
        'comment:delete',
    ],
    Role.EDITOR: [
        'workspace:view',
        'document:create',
        'document:view',
        'document:edit',
        'document:manage_versions',
        'comment:create',
        'comment:view',
        'comment:edit',
        'comment:delete',
    ],
    Role.VIEWER: [
        'workspace:view',
        'document:view',
        'comment:view',
        'comment:create',
    ],
}


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_workspaces'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='WorkspaceMember',
        through_fields=('workspace', 'user'),
        related_name='workspaces'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']

    def has_permission(self, user, permission):
        if user == self.owner:
            return True
        try:
            member = self.workspacemember_set.get(user=user)
            return permission in ROLE_PERMISSIONS.get(member.role, [])
        except WorkspaceMember.DoesNotExist:
            return False

    def get_user_role(self, user):
        if user == self.owner:
            return Role.ADMIN
        try:
            return self.workspacemember_set.get(user=user).role
        except WorkspaceMember.DoesNotExist:
            return None


class WorkspaceMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invited_members'
    )

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'user'],
                name='unique_workspace_member'
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.workspace.name} ({self.role})"


class InvitationStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    ACCEPTED = 'accepted', _('Accepted')
    DECLINED = 'declined', _('Declined')
    EXPIRED = 'expired', _('Expired')


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    token = models.CharField(max_length=64, unique=True)
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    status = models.CharField(max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('workspace', 'email', 'status')

    def __str__(self):
        return f"Invitation to {self.email} for {self.workspace.name}"

    @classmethod
    def generate_token(cls):
        return get_random_string(64)

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
