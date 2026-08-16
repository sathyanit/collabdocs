from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, TagViewSet

app_name = 'documents'

router = DefaultRouter()
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
]
