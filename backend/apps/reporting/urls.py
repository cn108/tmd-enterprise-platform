from __future__ import annotations

from django.urls import path

from apps.reporting import views

app_name = "reporting"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("reporting/<str:name>/export/", views.ReportExportView.as_view(), name="export"),
    path("reporting/<str:name>/", views.ReportView.as_view(), name="report"),
]
