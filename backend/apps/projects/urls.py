from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.projects import views

app_name = "projects"

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("project-locations", views.ProjectLocationViewSet, basename="project-location")
router.register("customer-contracts", views.CustomerContractViewSet, basename="customer-contract")
router.register("contract-revisions", views.ContractRevisionViewSet, basename="contract-revision")
router.register("project-budgets", views.ProjectBudgetViewSet, basename="project-budget")
router.register("project-milestones", views.ProjectMilestoneViewSet, basename="project-milestone")
router.register("project-costs", views.ProjectCostViewSet, basename="project-cost")

urlpatterns = [
    path("project-dashboard/", views.ProjectDashboardView.as_view(), name="project-dashboard"),
    path(
        "project-profitability/",
        views.ProjectProfitabilityView.as_view(),
        name="project-profitability",
    ),
    path(
        "project-documents/",
        views.ProjectDocumentListView.as_view(),
        name="project-documents",
    ),
    *router.urls,
]
