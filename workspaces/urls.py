from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    WorkspaceViewSet,
    InvitationViewSet,
    AcceptInvitationView,
    MyInvitationsView,
    RevokeInvitationView,
)

app_name = 'workspaces'

router = DefaultRouter()
router.register(r'', WorkspaceViewSet, basename='workspace')
router.register(r'invitations/list', InvitationViewSet, basename='invitation-list')

urlpatterns = [
    path('invitations/accept/', AcceptInvitationView.as_view(), name='accept-invitation'),
    path('invitations/me/', MyInvitationsView.as_view(), name='my-invitations'),
    path('invitations/<int:invitation_id>/revoke/', RevokeInvitationView.as_view(), name='revoke-invitation'),
    path('', include(router.urls)),
]
