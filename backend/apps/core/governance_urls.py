from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.core import governance_views

app_name = "governance"

router = DefaultRouter()
router.register("policies", governance_views.PolicyDecisionViewSet, basename="policy")
router.register(
    "approval-policies", governance_views.ApprovalPolicyViewSet, basename="approval-policy"
)
router.register("approvals", governance_views.ApprovalRecordViewSet, basename="approval-record")
router.register("audit-events", governance_views.AuditEventViewSet, basename="audit-event")
router.register(
    "tax-configuration", governance_views.TaxConfigurationViewSet, basename="tax-configuration"
)
router.register(
    "numbering-schemes", governance_views.NumberingSchemeViewSet, basename="numbering-scheme"
)

urlpatterns = [
    path("tax-profile/", governance_views.TaxProfileView.as_view(), name="tax-profile"),
    path(
        "configuration-report/",
        governance_views.ConfigurationReportView.as_view(),
        name="configuration-report",
    ),
    *router.urls,
]
