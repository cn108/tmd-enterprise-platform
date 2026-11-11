from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.organisation import views

app_name = "organisation"

router = DefaultRouter()
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("cost-centres", views.CostCentreViewSet, basename="cost-centre")

urlpatterns = router.urls
