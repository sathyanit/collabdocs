from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from workspaces.models import Workspace, WorkspaceMember, Role
from documents.models import Document, DocumentVersion, Tag, AuditLog

User = get_user_model()


class DocumentVersionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            first_name='Test',
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

    def test_document_creation_computes_version_number_per_document(self):
        # Create Doc 1
        res1 = self.client.post('/api/documents/', {
            'workspace': str(self.workspace.id),
            'title': 'Doc 1',
            'content': 'Initial content for doc 1',
            'status': 'draft'
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        doc1_id = res1.data['id']
        doc1 = Document.objects.get(id=doc1_id)

        self.assertEqual(doc1.versions.count(), 1)
        v1_doc1 = doc1.versions.first()
        self.assertEqual(v1_doc1.version_number, 1)
        self.assertEqual(v1_doc1.title, 'Doc 1')
        self.assertEqual(v1_doc1.content, 'Initial content for doc 1')
        self.assertEqual(v1_doc1.created_by, self.user)

        # Create Doc 2
        res2 = self.client.post('/api/documents/', {
            'workspace': str(self.workspace.id),
            'title': 'Doc 2',
            'content': 'Initial content for doc 2',
            'status': 'draft'
        })
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        doc2_id = res2.data['id']
        doc2 = Document.objects.get(id=doc2_id)

        # Doc 2 should also start at version 1 (not a global counter 2)
        self.assertEqual(doc2.versions.count(), 1)
        v1_doc2 = doc2.versions.first()
        self.assertEqual(v1_doc2.version_number, 1)

    def test_document_update_computes_per_document_version_number(self):
        # Create doc1
        res = self.client.post('/api/documents/', {
            'workspace': str(self.workspace.id),
            'title': 'Doc 1',
            'content': 'v1 content',
            'status': 'draft'
        })
        doc_id = res.data['id']

        # Update doc1 -> should become version 2
        res_update1 = self.client.patch(f'/api/documents/{doc_id}/', {
            'content': 'v2 content',
            'change_summary': 'Updated to v2',
            'save_version': True
        })
        self.assertEqual(res_update1.status_code, status.HTTP_200_OK)

        doc = Document.objects.get(id=doc_id)
        self.assertEqual(doc.versions.count(), 2)
        latest_version = doc.get_current_version()
        self.assertEqual(latest_version.version_number, 2)
        self.assertEqual(latest_version.content, 'v2 content')
        self.assertEqual(latest_version.change_summary, 'Updated to v2')

        # Update doc1 again -> should become version 3
        res_update2 = self.client.patch(f'/api/documents/{doc_id}/', {
            'content': 'v3 content',
            'change_summary': 'Updated to v3',
            'save_version': True
        })
        self.assertEqual(res_update2.status_code, status.HTTP_200_OK)
        self.assertEqual(doc.versions.count(), 3)
        self.assertEqual(doc.get_current_version().version_number, 3)

        # Update doc1 with save_version=False -> should remain version 3
        res_update3 = self.client.patch(f'/api/documents/{doc_id}/', {
            'title': 'Doc 1 Updated Title',
            'save_version': False
        })
        self.assertEqual(res_update3.status_code, status.HTTP_200_OK)
        self.assertEqual(doc.versions.count(), 3)
        self.assertEqual(doc.get_current_version().version_number, 3)

    def test_restore_version_creates_next_version_number(self):
        # Create doc
        res = self.client.post('/api/documents/', {
            'workspace': str(self.workspace.id),
            'title': 'Doc Original',
            'content': 'Original Content',
        })
        doc_id = res.data['id']
        doc = Document.objects.get(id=doc_id)
        v1 = doc.versions.get(version_number=1)

        # Update to v2
        self.client.patch(f'/api/documents/{doc_id}/', {
            'title': 'Doc Modified',
            'content': 'Modified Content',
            'save_version': True
        })
        self.assertEqual(doc.versions.count(), 2)

        # Restore v1
        res_restore = self.client.post(f'/api/documents/{doc_id}/restore_version/', {
            'version_id': str(v1.id)
        })
        self.assertEqual(res_restore.status_code, status.HTTP_200_OK)

        doc.refresh_from_db()
        self.assertEqual(doc.title, 'Doc Original')
        self.assertEqual(doc.content, 'Original Content')
        self.assertEqual(doc.versions.count(), 3)
        self.assertEqual(doc.get_current_version().version_number, 3)

    def test_tag_model_and_many_to_many_relationship(self):
        import uuid
        from django.db import IntegrityError, transaction

        # Create tag
        tag = Tag.objects.create(name='python')
        self.assertIsInstance(tag.id, uuid.UUID)
        self.assertEqual(str(tag), 'python')

        # Unique name constraint
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Tag.objects.create(name='python')

        # 1. Associate documents using tag.documents.add(doc)
        doc1 = Document.objects.create(
            workspace=self.workspace,
            title='Python Guide',
            created_by=self.user,
            last_edited_by=self.user
        )
        tag.documents.add(doc1)

        # 2. Associate documents using doc.tags.add(tag)
        doc2 = Document.objects.create(
            workspace=self.workspace,
            title='Django Guide',
            created_by=self.user,
            last_edited_by=self.user
        )
        doc2.tags.add(tag)

        # Access from tag
        self.assertIn(doc1, tag.documents.all())
        self.assertIn(doc2, tag.documents.all())

        # Access from document (related_name='tags')
        self.assertIn(tag, doc1.tags.all())
        self.assertIn(tag, doc2.tags.all())

        # Filter documents by tag name: Document.objects.filter(tags__name='python')
        python_docs = Document.objects.filter(tags__name='python')
        self.assertEqual(python_docs.count(), 2)
        self.assertIn(doc1, python_docs)
        self.assertIn(doc2, python_docs)

    def test_tag_api(self):
        # Create tag via API
        res = self.client.post('/api/documents/tags/', {'name': 'django'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        tag_id = res.data['id']

        tag_django = Tag.objects.get(id=tag_id)
        doc = Document.objects.create(
            workspace=self.workspace,
            title='Web Development with Django',
            created_by=self.user,
            last_edited_by=self.user
        )
        doc.tags.add(tag_django)

        # List tags
        res_list = self.client.get('/api/documents/tags/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        results = res_list.data['results'] if isinstance(res_list.data, dict) and 'results' in res_list.data else res_list.data
        self.assertTrue(any(t['name'] == 'django' for t in results))

        # Filter documents by tag via API
        res_docs_tag = self.client.get('/api/documents/?tag=django')
        self.assertEqual(res_docs_tag.status_code, status.HTTP_200_OK)
        doc_results = res_docs_tag.data['results'] if isinstance(res_docs_tag.data, dict) and 'results' in res_docs_tag.data else res_docs_tag.data
        self.assertTrue(any(d['id'] == str(doc.id) for d in doc_results))

    def test_audit_log_post_save_signal(self):
        import uuid

        editor = User.objects.create_user(
            email='editor@example.com',
            password='password123',
            first_name='Editor',
            last_name='User'
        )

        # 1. Document creation should write an AuditLog with action='created'
        doc = Document.objects.create(
            workspace=self.workspace,
            title='Audit Log Test Doc',
            content='Initial content',
            created_by=self.user,
            last_edited_by=self.user
        )

        create_log = AuditLog.objects.filter(model_name='Document', object_id=str(doc.id)).order_by('timestamp').first()
        self.assertIsNotNone(create_log)
        self.assertIsInstance(create_log.id, uuid.UUID)
        self.assertEqual(create_log.action, 'created')
        self.assertEqual(create_log.actor, self.user)
        self.assertEqual(create_log.model_name, 'Document')
        self.assertEqual(create_log.object_id, str(doc.id))

        # 2. Document update should write an AuditLog with action='updated'
        doc.title = 'Audit Log Test Doc Updated'
        doc.last_edited_by = editor
        doc.save()

        update_log = AuditLog.objects.filter(model_name='Document', object_id=str(doc.id)).order_by('-timestamp').first()
        self.assertIsNotNone(update_log)
        self.assertEqual(update_log.action, 'updated')
        self.assertEqual(update_log.actor, editor)

        # 3. Deleting actor user sets actor=NULL (on_delete=SET_NULL)
        editor.delete()
        update_log.refresh_from_db()
        self.assertIsNone(update_log.actor)
        self.assertIn('Anonymous', str(update_log))

        # 4. Document audit_logs API endpoint
        res = self.client.get(f'/api/documents/{doc.id}/audit_logs/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        logs = res.data['results'] if isinstance(res.data, dict) and 'results' in res.data else res.data
        self.assertTrue(len(logs) >= 2)
