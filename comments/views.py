from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend

from .models import Comment, Reaction
from .serializers import (
    CommentSerializer,
    CommentDetailSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
    ReactionSerializer,
    ReactionCreateSerializer,
)
from workspaces.permissions import (
    CanViewComment,
    CanCreateComment,
    CanEditComment,
    CanDeleteComment,
)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['document', 'is_resolved', 'parent']
    search_fields = ['content']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        user = self.request.user
        qs = Comment.objects.filter(
            document__workspace__in=user.workspaces.all(),
            deleted_at__isnull=True
        ).annotate(
            replies_count=Count('replies', filter=Q(replies__deleted_at__isnull=True))
        ).distinct()
        if self.action == 'list':
            parent_filter = self.request.query_params.get('parent')
            if parent_filter is None:
                qs = qs.filter(parent__isnull=True)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CommentUpdateSerializer
        elif self.action == 'retrieve':
            return CommentDetailSerializer
        return CommentSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [CanCreateComment()]
        elif self.action in ['list', 'retrieve']:
            return [CanViewComment()]
        elif self.action in ['update', 'partial_update']:
            return [CanEditComment()]
        elif self.action == 'destroy':
            return [CanDeleteComment()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        comment.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def resolve(self, request, pk=None):
        comment = self.get_object()
        workspace = comment.document.workspace
        user = request.user
        if not workspace.has_permission(user, 'comment:delete') and comment.author != user:
            return Response(
                {'detail': 'You do not have permission to resolve this comment.'},
                status=status.HTTP_403_FORBIDDEN
            )
        comment.resolve(user)
        return Response(CommentDetailSerializer(comment, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def unresolve(self, request, pk=None):
        comment = self.get_object()
        workspace = comment.document.workspace
        user = request.user
        if not workspace.has_permission(user, 'comment:delete') and comment.author != user:
            return Response(
                {'detail': 'You do not have permission to unresolve this comment.'},
                status=status.HTTP_403_FORBIDDEN
            )
        comment.unresolve()
        return Response(CommentDetailSerializer(comment, context={'request': request}).data)

    @action(detail=True, methods=['get'], permission_classes=[CanViewComment])
    def replies(self, request, pk=None):
        comment = self.get_object()
        replies = comment.replies.filter(deleted_at__isnull=True).order_by('created_at').annotate(
            replies_count=Count('replies', filter=Q(replies__deleted_at__isnull=True))
        )
        page = self.paginate_queryset(replies)
        if page is not None:
            serializer = CommentSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = CommentSerializer(replies, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], permission_classes=[CanViewComment])
    def reactions(self, request, pk=None):
        comment = self.get_object()
        if request.method == 'GET':
            reactions = comment.reactions.all()
            serializer = ReactionSerializer(reactions, many=True, context={'request': request})
            return Response(serializer.data)
        else:
            if not comment.document.workspace.has_permission(request.user, 'comment:create'):
                return Response(
                    {'detail': 'You do not have permission to react to comments.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            serializer = ReactionCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            reaction, created = Reaction.objects.get_or_create(
                comment=comment,
                user=request.user,
                reaction_type=serializer.validated_data['reaction_type']
            )
            if not created:
                reaction.delete()
                return Response(
                    {'detail': 'Reaction removed.'},
                    status=status.HTTP_200_OK
                )
            return Response(
                ReactionSerializer(reaction, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
