from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.projects import views

app_name = "projects"

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("project-locations", views.ProjectLocationViewSet, basename="project-location")
router.register("customer-contracts", views.CustomerContractViewSet, basename="customer-contract")
router.register("contract-revisions", views.ContractRevisionViewSet, basename="contract-revision")

urlpatterns = router.urls
