from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.documents import views

app_name = "documents"

router = DefaultRouter()
router.register("document-categories", views.DocumentCategoryViewSet, basename="document-category")
router.register("documents", views.DocumentViewSet, basename="document")
router.register("document-links", views.DocumentLinkViewSet, basename="document-link")

urlpatterns = router.urls
