from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounting import views

app_name = "accounting"

router = DefaultRouter()
router.register("accounts", views.AccountViewSet, basename="account")
router.register("account-roles", views.AccountRoleViewSet, basename="account-role")
router.register(
    "account-role-mappings", views.AccountRoleMappingViewSet, basename="account-role-mapping"
)
router.register("fiscal-years", views.FiscalYearViewSet, basename="fiscal-year")
router.register("accounting-periods", views.AccountingPeriodViewSet, basename="accounting-period")
router.register("journals", views.JournalViewSet, basename="journal")
router.register("opening-balances", views.OpeningBalanceViewSet, basename="opening-balance")
router.register("posting-rules", views.PostingRuleViewSet, basename="posting-rule")
router.register("financial-events", views.FinancialEventViewSet, basename="financial-event")

urlpatterns = [
    path(
        "accounting-settings/",
        views.AccountingSettingsView.as_view(),
        name="accounting-settings",
    ),
    path("trial-balance/", views.TrialBalanceView.as_view(), name="trial-balance"),
    path(
        "financial-statements/",
        views.FinancialStatementsView.as_view(),
        name="financial-statements",
    ),
    path("general-ledger/", views.GeneralLedgerView.as_view(), name="general-ledger"),
    *router.urls,
]
