from rest_framework import serializers
from django.conf import settings

from .models import Comment, Reaction
from accounts.serializers import UserSerializer


class ReactionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    reaction_display = serializers.CharField(source='get_reaction_type_display', read_only=True)

    class Meta:
        model = Reaction
        fields = ('id', 'user', 'reaction_type', 'reaction_display', 'created_at')
        read_only_fields = ('id', 'user', 'created_at')


class ReactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = ('reaction_type',)


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    replies_count = serializers.IntegerField(read_only=True)
    reactions_summary = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            'id', 'document', 'author', 'parent', 'content',
            'is_resolved', 'resolved_at', 'resolved_by',
            'is_edited', 'deleted_at', 'created_at', 'updated_at',
            'replies_count', 'reactions_summary', 'is_author'
        )
        read_only_fields = (
            'id', 'author', 'is_resolved', 'resolved_at', 'resolved_by',
            'is_edited', 'deleted_at', 'created_at', 'updated_at'
        )

    def get_reactions_summary(self, obj):
        from django.db.models import Count
        reactions = obj.reactions.values('reaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        return list(reactions)

    def get_is_author(self, obj):
        user = self.context['request'].user
        return obj.author == user


class CommentDetailSerializer(CommentSerializer):
    replies = serializers.SerializerMethodField()
    reactions = ReactionSerializer(many=True, read_only=True)

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ('replies', 'reactions')

    def get_replies(self, obj):
        replies = obj.replies.filter(deleted_at__isnull=True).order_by('created_at')
        return CommentSerializer(replies, many=True, context=self.context).data


class CommentCreateSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'document', 'parent', 'content', 'author', 'created_at')
        read_only_fields = ('id', 'author', 'created_at')

    def validate_document(self, value):
        user = self.context['request'].user
        if not value.workspace.has_permission(user, 'comment:create'):
            raise serializers.ValidationError(
                "You don't have permission to comment on documents in this workspace."
            )
        return value

    def validate_parent(self, value):
        if value and self.initial_data.get('document') and str(value.document_id) != str(self.initial_data.get('document')):
            raise serializers.ValidationError("Parent comment must be on the same document.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        comment = Comment.objects.create(author=user, **validated_data)
        return comment


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ('content',)

    def update(self, instance, validated_data):
        instance.is_edited = True
        return super().update(instance, validated_data)
