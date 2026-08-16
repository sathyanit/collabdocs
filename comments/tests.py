import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from workspaces.models import Workspace, WorkspaceMember, Role
from documents.models import Document
from comments.models import Comment, Reaction

User = get_user_model()


class CommentModelTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='author@example.com',
            password='password123',
            first_name='Author',
            last_name='User'
        )
        self.client.force_authenticate(user=self.user)

        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            owner=self.user
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=Role.ADMIN
        )
        self.document = Document.objects.create(
            workspace=self.workspace,
            title='Test Document',
            content='Document content',
            created_by=self.user,
            last_edited_by=self.user
        )

    def test_comment_fields_and_types(self):
        comment = Comment.objects.create(
            document=self.document,
            author=self.user,
            content='This is a top-level comment.'
        )
        # ID is UUID
        self.assertIsInstance(comment.id, uuid.UUID)
        self.assertEqual(comment.document, self.document)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.content, 'This is a top-level comment.')
        self.assertIsNone(comment.parent)
        self.assertTrue(comment.is_top_level)
        self.assertFalse(comment.is_reply)
        self.assertIsNotNone(comment.created_at)

    def test_threaded_replies_and_parent_set_null(self):
        parent_comment = Comment.objects.create(
            document=self.document,
            author=self.user,
            content='Parent comment'
        )
        self.assertTrue(parent_comment.is_top_level)

        reply = Comment.objects.create(
            document=self.document,
            author=self.user,
            parent=parent_comment,
            content='Reply comment'
        )

        self.assertEqual(reply.parent, parent_comment)
        self.assertFalse(reply.is_top_level)
        self.assertTrue(reply.is_reply)
        self.assertIn(reply, parent_comment.replies.all())

        # Deleting parent comment should SET_NULL on reply.parent
        parent_comment.delete()
        reply.refresh_from_db()
        self.assertIsNone(reply.parent)

    def test_author_set_null_on_user_delete(self):
        other_user = User.objects.create_user(
            email='other_author@example.com',
            password='password123',
            first_name='Other',
            last_name='Author'
        )
        comment = Comment.objects.create(
            document=self.document,
            author=other_user,
            content='Comment to test author deletion'
        )
        other_user.delete()
        comment.refresh_from_db()
        self.assertIsNone(comment.author)
        self.assertEqual(str(comment), f"Comment by Unknown on {self.document.title}")

    def test_document_cascade_delete(self):
        comment = Comment.objects.create(
            document=self.document,
            author=self.user,
            content='Comment to test document cascade'
        )
        comment_id = comment.id
        self.document.delete()
        self.assertFalse(Comment.objects.filter(id=comment_id).exists())

    def test_comment_api_endpoints(self):
        # Create comment
        res = self.client.post('/api/comments/', {
            'document': str(self.document.id),
            'content': 'API Comment'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        comment_id = res.data['id']

        # Create threaded reply
        res_reply = self.client.post('/api/comments/', {
            'document': str(self.document.id),
            'parent': comment_id,
            'content': 'API Reply'
        })
        self.assertEqual(res_reply.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(res_reply.data['parent']), comment_id)
