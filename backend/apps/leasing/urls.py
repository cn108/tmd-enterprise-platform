from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.leasing import views

app_name = "leasing"

router = DefaultRouter()
router.register(
    "equipment-categories", views.EquipmentCategoryViewSet, basename="equipment-category"
)
router.register("equipment", views.EquipmentViewSet, basename="equipment")
router.register("equipment-rates", views.EquipmentRateViewSet, basename="equipment-rate")
router.register("rental-agreements", views.RentalAgreementViewSet, basename="rental-agreement")
router.register(
    "equipment-reservations",
    views.EquipmentReservationViewSet,
    basename="equipment-reservation",
)
router.register(
    "equipment-movements", views.EquipmentMovementViewSet, basename="equipment-movement"
)
router.register(
    "equipment-inspections",
    views.EquipmentInspectionViewSet,
    basename="equipment-inspection",
)
router.register(
    "equipment-maintenance",
    views.EquipmentMaintenanceViewSet,
    basename="equipment-maintenance",
)

urlpatterns = [
    path(
        "equipment-utilisation/",
        views.EquipmentUtilisationView.as_view(),
        name="equipment-utilisation",
    ),
    path("equipment-warnings/", views.EquipmentWarningsView.as_view(), name="equipment-warnings"),
    path(
        "equipment-availability/",
        views.EquipmentAvailabilityView.as_view(),
        name="equipment-availability",
    ),
    *router.urls,
]
