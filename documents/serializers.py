from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Document, DocumentVersion, DocumentStatus, DocumentCollaborator
from accounts.serializers import UserSerializer
from workspaces.serializers import WorkspaceSerializer

User = get_user_model()


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = (
            'id', 'title', 'content', 'version_number',
            'change_summary', 'created_by', 'created_at'
        )
        read_only_fields = ('id', 'version_number', 'created_at', 'created_by')


class DocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ('id', 'workspace', 'parent', 'title', 'content', 'status')
        read_only_fields = ('id',)

    def validate_workspace(self, value):
        user = self.context['request'].user
        if not value.has_permission(user, 'document:create'):
            raise serializers.ValidationError("You don't have permission to create documents in this workspace.")
        return value

    def validate_parent(self, value):
        if value and value.workspace != self.initial_data.get('workspace'):
            raise serializers.ValidationError("Parent document must be in the same workspace.")
        return value


class DocumentSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    last_edited_by = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    workspace = WorkspaceSerializer(read_only=True)
    workspace_id = serializers.PrimaryKeyRelatedField(
        queryset=Document._meta.get_field('workspace').related_model.objects.all(),
        source='workspace',
        write_only=True,
        required=False
    )
    versions_count = serializers.IntegerField(read_only=True)
    children_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Document
        fields = (
            'id', 'workspace', 'workspace_id', 'parent', 'title', 'content',
            'status', 'status_display', 'created_by', 'last_edited_by',
            'is_pinned', 'order', 'created_at', 'updated_at',
            'versions_count', 'children_count', 'comments_count'
        )
        read_only_fields = (
            'id', 'created_by', 'last_edited_by', 'created_at', 'updated_at',
            'versions_count', 'children_count', 'comments_count'
        )


class DocumentDetailSerializer(DocumentSerializer):
    versions = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ('versions', 'children')

    def get_versions(self, obj):
        versions = obj.versions.all()[:10]
        return DocumentVersionSerializer(versions, many=True, context=self.context).data

    def get_children(self, obj):
        children = obj.children.all().order_by('order', '-updated_at')
        return DocumentSerializer(children, many=True, context=self.context).data


class DocumentUpdateSerializer(serializers.ModelSerializer):
    save_version = serializers.BooleanField(default=True, write_only=True)
    change_summary = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Document
        fields = ('title', 'content', 'status', 'is_pinned', 'order', 'parent', 'save_version', 'change_summary')

    def update(self, instance, validated_data):
        save_version = validated_data.pop('save_version', True)
        change_summary = validated_data.pop('change_summary', '')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        user = self.context['request'].user
        instance.last_edited_by = user
        instance.save()

        if save_version:
            DocumentVersion.objects.create(
                document=instance,
                title=instance.title,
                content=instance.content,
                version_number=instance.versions.count() + 1,
                change_summary=change_summary,
                created_by=user
            )

        return instance


class RestoreVersionSerializer(serializers.Serializer):
    version_id = serializers.IntegerField(required=True)

    def validate_version_id(self, value):
        document = self.context['document']
        try:
            version = document.versions.get(id=value)
        except DocumentVersion.DoesNotExist:
            raise serializers.ValidationError("Version not found.")
        self.version = version
        return value

    def save(self, **kwargs):
        document = self.context['document']
        user = self.context['request'].user
        self.version.restore(user)
        return document


class DocumentCollaboratorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )

    class Meta:
        model = DocumentCollaborator
        fields = ('id', 'user', 'user_id', 'can_edit', 'added_at', 'added_by')
        read_only_fields = ('id', 'added_at', 'added_by')
