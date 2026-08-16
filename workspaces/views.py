from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q

from .models import Workspace, WorkspaceMember, Invitation, Role, InvitationStatus
from .serializers import (
    WorkspaceSerializer,
    WorkspaceCreateSerializer,
    WorkspaceDetailSerializer,
    WorkspaceMemberSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    InvitationAcceptSerializer,
    MemberRoleUpdateSerializer,
)
from .permissions import (
    CanViewWorkspace,
    CanEditWorkspace,
    CanDeleteWorkspace,
    CanInviteToWorkspace,
    CanManageMembers,
    CanManageRoles,
    IsWorkspaceOwner,
)


class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()

    def get_queryset(self):
        user = self.request.user
        return Workspace.objects.filter(
            Q(owner=user) | Q(members=user)
        ).annotate(
            members_count=Count('members')
        ).distinct().order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkspaceCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return WorkspaceDetailSerializer
        return WorkspaceSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            return [CanEditWorkspace()]
        elif self.action == 'destroy':
            return [CanDeleteWorkspace()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=True, methods=['post'], permission_classes=[CanInviteToWorkspace])
    def invite(self, request, pk=None):
        workspace = self.get_object()
        serializer = InvitationCreateSerializer(
            data=request.data,
            context={'request': request, 'workspace': workspace}
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        return Response(
            InvitationSerializer(invitation, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], permission_classes=[CanViewWorkspace])
    def invitations(self, request, pk=None):
        workspace = self.get_object()
        invitations = workspace.invitations.filter(status=InvitationStatus.PENDING)
        serializer = InvitationSerializer(invitations, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[CanViewWorkspace])
    def members(self, request, pk=None):
        workspace = self.get_object()
        members = workspace.workspacemember_set.select_related('user').all()
        serializer = WorkspaceMemberSerializer(members, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[CanManageRoles],
            url_path='members/(?P<member_id>[^/.]+)/role')
    def update_member_role(self, request, pk=None, member_id=None):
        workspace = self.get_object()
        try:
            member = workspace.workspacemember_set.get(id=member_id)
        except WorkspaceMember.DoesNotExist:
            return Response(
                {'detail': 'Member not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if member.user == workspace.owner:
            return Response(
                {'detail': 'Cannot change workspace owner role.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = MemberRoleUpdateSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WorkspaceMemberSerializer(member, context={'request': request}).data)

    @action(detail=True, methods=['delete'], permission_classes=[CanManageMembers],
            url_path='members/(?P<member_id>[^/.]+)')
    def remove_member(self, request, pk=None, member_id=None):
        workspace = self.get_object()
        try:
            member = workspace.workspacemember_set.get(id=member_id)
        except WorkspaceMember.DoesNotExist:
            return Response(
                {'detail': 'Member not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if member.user == workspace.owner:
            return Response(
                {'detail': 'Cannot remove workspace owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[CanEditWorkspace])
    def activate(self, request, pk=None):
        workspace = self.get_object()
        workspace.is_active = True
        workspace.save()
        return Response(WorkspaceDetailSerializer(workspace, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditWorkspace])
    def deactivate(self, request, pk=None):
        workspace = self.get_object()
        workspace.is_active = False
        workspace.save()
        return Response(WorkspaceDetailSerializer(workspace, context={'request': request}).data)


class InvitationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Invitation.objects.filter(
            workspace__in=user.workspaces.all()
        ) | Invitation.objects.filter(inviter=user)


class AcceptInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        return Response({
            'detail': 'Invitation accepted successfully.',
            'workspace_id': workspace.id,
            'workspace_name': workspace.name
        }, status=status.HTTP_200_OK)


class MyInvitationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        invitations = Invitation.objects.filter(
            email=request.user.email,
            status=InvitationStatus.PENDING
        )
        serializer = InvitationSerializer(invitations, many=True, context={'request': request})
        return Response(serializer.data)


class RevokeInvitationView(APIView):
    permission_classes = [CanManageMembers]

    def delete(self, request, invitation_id):
        try:
            invitation = Invitation.objects.get(id=invitation_id)
        except Invitation.DoesNotExist:
            return Response(
                {'detail': 'Invitation not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        self.check_object_permissions(request, invitation.workspace)
        if invitation.status != InvitationStatus.PENDING:
            return Response(
                {'detail': 'Only pending invitations can be revoked.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        invitation.status = InvitationStatus.DECLINED
        invitation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
