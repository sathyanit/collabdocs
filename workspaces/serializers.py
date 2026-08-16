from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import Workspace, WorkspaceMember, Invitation, Role, InvitationStatus
from accounts.serializers import UserSerializer

User = get_user_model()


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True,
        required=False
    )
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ('id', 'user', 'user_id', 'role', 'role_display', 'joined_at', 'invited_by')
        read_only_fields = ('id', 'joined_at', 'invited_by')


class WorkspaceSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    members_count = serializers.IntegerField(read_only=True)
    user_role = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            'id', 'name', 'owner', 'is_active',
            'created_at', 'members_count', 'user_role', 'is_owner'
        )
        read_only_fields = ('id', 'owner', 'created_at', 'members_count')

    def get_user_role(self, obj):
        user = self.context['request'].user
        return obj.get_user_role(user)

    def get_is_owner(self, obj):
        user = self.context['request'].user
        return user == obj.owner


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ('id', 'name')
        read_only_fields = ('id',)

    def create(self, validated_data):
        user = self.context['request'].user
        with transaction.atomic():
            workspace = Workspace.objects.create(owner=user, **validated_data)
            WorkspaceMember.objects.create(
                workspace=workspace,
                user=user,
                role=Role.ADMIN,
                invited_by=None
            )
            return workspace


class WorkspaceDetailSerializer(WorkspaceSerializer):
    members = serializers.SerializerMethodField()

    class Meta(WorkspaceSerializer.Meta):
        fields = WorkspaceSerializer.Meta.fields + ('members',)

    def get_members(self, obj):
        members = obj.workspacemember_set.select_related('user').all()
        return WorkspaceMemberSerializer(members, many=True, context=self.context).data


class InvitationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ('id', 'email', 'role')

    def validate_email(self, value):
        workspace = self.context.get('workspace')
        if workspace and workspace.members.filter(email=value).exists():
            raise serializers.ValidationError("User is already a member of this workspace.")
        existing = Invitation.objects.filter(
            workspace=workspace,
            email=value,
            status=InvitationStatus.PENDING
        ).exists()
        if existing:
            raise serializers.ValidationError("An invitation already exists for this email.")
        return value

    def create(self, validated_data):
        workspace = self.context['workspace']
        inviter = self.context['request'].user
        token = Invitation.generate_token()
        expires_at = timezone.now() + timedelta(days=7)
        invitation = Invitation.objects.create(
            workspace=workspace,
            token=token,
            inviter=inviter,
            expires_at=expires_at,
            **validated_data
        )
        return invitation


class InvitationSerializer(serializers.ModelSerializer):
    inviter = UserSerializer(read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Invitation
        fields = (
            'id', 'email', 'role', 'role_display', 'workspace', 'workspace_name',
            'inviter', 'status', 'status_display', 'expires_at',
            'accepted_at', 'created_at'
        )
        read_only_fields = ('id', 'token', 'inviter', 'status', 'expires_at', 'accepted_at', 'created_at')


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)

    def validate_token(self, value):
        try:
            invitation = Invitation.objects.get(token=value)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token.")

        if invitation.status != InvitationStatus.PENDING:
            raise serializers.ValidationError("This invitation has already been processed.")

        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            invitation.save()
            raise serializers.ValidationError("This invitation has expired.")

        user = self.context['request'].user
        if invitation.workspace.members.filter(id=user.id).exists():
            raise serializers.ValidationError("You are already a member of this workspace.")

        self.invitation = invitation
        return value

    def save(self, **kwargs):
        invitation = self.invitation
        user = self.context['request'].user
        WorkspaceMember.objects.create(
            workspace=invitation.workspace,
            user=user,
            role=invitation.role,
            invited_by=invitation.inviter
        )
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.save()
        return invitation.workspace


class MemberRoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceMember
        fields = ('role',)
