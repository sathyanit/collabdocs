import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework import status

from workspaces.models import Workspace, WorkspaceMember, Role
from documents.models import DocumentStatus

User = get_user_model()


class WorkspaceConstraintsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='owner@example.com',
            password='password123',
            first_name='Workspace',
            last_name='Owner'
        )
        self.client.force_authenticate(user=self.user)

    def test_workspace_creation_adds_owner_as_admin_member(self):
        res = self.client.post('/api/workspaces/', {'name': 'Engineering'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        workspace_id = res.data['id']

        workspace = Workspace.objects.get(id=workspace_id)
        self.assertEqual(workspace.owner, self.user)
        # Check is_active default
        self.assertTrue(workspace.is_active)

        # Check owner is added as admin member
        member = WorkspaceMember.objects.filter(workspace=workspace, user=self.user).first()
        self.assertIsNotNone(member)
        self.assertEqual(member.role, Role.ADMIN)
        self.assertEqual(member.role, 'admin')

    def test_workspace_member_unique_constraint(self):
        workspace = Workspace.objects.create(name='Design Team', owner=self.user)
        WorkspaceMember.objects.create(workspace=workspace, user=self.user, role=Role.ADMIN)

        # Attempting to add the same user to the same workspace should raise IntegrityError
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                WorkspaceMember.objects.create(workspace=workspace, user=self.user, role=Role.EDITOR)

    def test_text_choices_enums(self):
        # Verify Role choices
        self.assertEqual(Role.ADMIN, 'admin')
        self.assertEqual(Role.EDITOR, 'editor')
        self.assertEqual(Role.VIEWER, 'viewer')

        # Verify DocumentStatus choices
        self.assertEqual(DocumentStatus.DRAFT, 'draft')
        self.assertEqual(DocumentStatus.PUBLISHED, 'published')
        self.assertEqual(DocumentStatus.ARCHIVED, 'archived')
