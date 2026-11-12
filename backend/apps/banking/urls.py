from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.banking import views

app_name = "banking"

router = DefaultRouter()
router.register("company-bank-accounts", views.BankAccountViewSet, basename="company-bank-account")
router.register("bank-statements", views.BankStatementViewSet, basename="bank-statement")
router.register("statement-lines", views.StatementLineViewSet, basename="statement-line")
router.register("bank-transactions", views.BankTransactionViewSet, basename="bank-transaction")
router.register("reconciliations", views.ReconciliationViewSet, basename="reconciliation")
router.register("bank-transfers", views.BankTransferViewSet, basename="bank-transfer")
router.register("cash-accounts", views.CashAccountViewSet, basename="cash-account")
router.register("cash-vouchers", views.CashVoucherViewSet, basename="cash-voucher")
router.register(
    "petty-cash-replenishments",
    views.PettyCashReplenishmentViewSet,
    basename="petty-cash-replenishment",
)

urlpatterns = [
    path("banking-settings/", views.BankingSettingsView.as_view(), name="banking-settings"),
    path("banking-summary/", views.BankingSummaryView.as_view(), name="banking-summary"),
    path(
        "banking-reconciliation-report/",
        views.ReconciliationReportView.as_view(),
        name="banking-reconciliation-report",
    ),
    path(
        "banking-unmatched-transactions/",
        views.UnmatchedTransactionsView.as_view(),
        name="banking-unmatched-transactions",
    ),
    path(
        "banking-match-suggestions/",
        views.MatchSuggestionsView.as_view(),
        name="banking-match-suggestions",
    ),
    path("banking-cash-position/", views.CashPositionView.as_view(), name="banking-cash-position"),
    *router.urls,
]
