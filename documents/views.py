from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend

from .models import Document, DocumentVersion, DocumentStatus, DocumentCollaborator
from .serializers import (
    DocumentSerializer,
    DocumentCreateSerializer,
    DocumentDetailSerializer,
    DocumentUpdateSerializer,
    DocumentVersionSerializer,
    RestoreVersionSerializer,
    DocumentCollaboratorSerializer,
)
from workspaces.permissions import (
    CanCreateDocument,
    CanViewDocument,
    CanEditDocument,
    CanDeleteDocument,
    CanManageVersions,
)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['workspace', 'status', 'parent', 'is_pinned']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at', 'title', 'order']

    def get_queryset(self):
        user = self.request.user
        return Document.objects.filter(
            workspace__in=user.workspaces.all()
        ).annotate(
            versions_count=Count('versions', distinct=True),
            children_count=Count('children', distinct=True),
            comments_count=Count('comments', distinct=True),
        ).distinct().order_by('-is_pinned', 'order', '-updated_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DocumentUpdateSerializer
        elif self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            return [CanViewDocument()]
        elif self.action in ['update', 'partial_update']:
            return [CanEditDocument()]
        elif self.action == 'destroy':
            return [CanDeleteDocument()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        user = self.request.user
        instance = serializer.save(created_by=user, last_edited_by=user)
        DocumentVersion.objects.create(
            document=instance,
            title=instance.title,
            content=instance.content,
            version_number=1,
            created_by=user
        )
        return instance

    @action(detail=True, methods=['get'], permission_classes=[CanViewDocument])
    def versions(self, request, pk=None):
        document = self.get_object()
        versions = document.versions.all()
        page = self.paginate_queryset(versions)
        if page is not None:
            serializer = DocumentVersionSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = DocumentVersionSerializer(versions, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[CanViewDocument],
            url_path='versions/(?P<version_id>[^/.]+)')
    def version_detail(self, request, pk=None, version_id=None):
        document = self.get_object()
        try:
            version = document.versions.get(id=version_id)
        except DocumentVersion.DoesNotExist:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DocumentVersionSerializer(version, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[CanManageVersions])
    def restore_version(self, request, pk=None):
        document = self.get_object()
        serializer = RestoreVersionSerializer(
            data=request.data,
            context={'document': document, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditDocument])
    def publish(self, request, pk=None):
        document = self.get_object()
        document.status = DocumentStatus.PUBLISHED
        document.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditDocument])
    def archive(self, request, pk=None):
        document = self.get_object()
        document.status = DocumentStatus.ARCHIVED
        document.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditDocument])
    def draft(self, request, pk=None):
        document = self.get_object()
        document.status = DocumentStatus.DRAFT
        document.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditDocument])
    def pin(self, request, pk=None):
        document = self.get_object()
        document.is_pinned = True
        document.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[CanEditDocument])
    def unpin(self, request, pk=None):
        document = self.get_object()
        document.is_pinned = False
        document.save()
        return Response(DocumentDetailSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['get', 'post'], permission_classes=[CanViewDocument])
    def collaborators(self, request, pk=None):
        document = self.get_object()
        if request.method == 'GET':
            collaborators = document.collaborators.all()
            serializer = DocumentCollaboratorSerializer(collaborators, many=True, context={'request': request})
            return Response(serializer.data)
        else:
            if not document.workspace.has_permission(request.user, 'workspace:manage_members'):
                return Response(
                    {'detail': 'You do not have permission to add collaborators.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            serializer = DocumentCollaboratorSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save(document=document, added_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='collaborators/(?P<collab_id>[^/.]+)',
            permission_classes=[CanEditDocument])
    def remove_collaborator(self, request, pk=None, collab_id=None):
        document = self.get_object()
        try:
            collab = document.collaborators.get(id=collab_id)
        except DocumentCollaborator.DoesNotExist:
            return Response({'detail': 'Collaborator not found.'}, status=status.HTTP_404_NOT_FOUND)
        collab.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
