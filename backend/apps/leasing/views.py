from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import create_audit_event
from apps.documents.models import DocumentLink
from apps.documents.services import attach_upload
from apps.leasing.models import (
    Equipment,
    EquipmentCategory,
    EquipmentInspection,
    EquipmentMaintenance,
    EquipmentMovement,
    EquipmentRate,
    EquipmentReservation,
    RentalAgreement,
)
from apps.leasing.serializers import (
    EquipmentCategorySerializer,
    EquipmentInspectionSerializer,
    EquipmentMaintenanceSerializer,
    EquipmentMovementSerializer,
    EquipmentRateSerializer,
    EquipmentReservationSerializer,
    EquipmentSerializer,
    RentalAgreementSerializer,
)
from apps.leasing.workflows import (
    LeasingConflict,
    approve_agreement,
    availability_rows,
    check_availability,
    complete_maintenance,
    dispatch_equipment,
    rental_inspection,
    return_equipment,
    utilisation_rows,
    warning_rows,
)
from apps.procurement.numbering import next_number
from shared.exceptions import error_response
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: LeasingConflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


def _paged(request, rows: list[dict]) -> Response:
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
        size = min(max(int(request.query_params.get("page_size", "25")), 1), 100)
    except ValueError:
        page, size = 1, 25
    start = (page - 1) * size
    return Response({"count": len(rows), "results": rows[start : start + size]})


def _dates(request) -> tuple[date, date]:
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.query_params.get("start") or today.isoformat())
        end = date.fromisoformat(
            request.query_params.get("end") or (today + timedelta(days=30)).isoformat()
        )
    except ValueError:
        start, end = today, today + timedelta(days=30)
    return start, end


class LeasingPermissionMixin:
    view_permission = ""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS and self.view_permission:
            _require(request, self.view_permission)


class EquipmentCategoryViewSet(LeasingPermissionMixin, MasterDataViewSet):
    view_permission = "leasing.view_equipmentcategory"
    queryset = EquipmentCategory.objects.all()
    serializer_class = EquipmentCategorySerializer
    search_fields = ("code", "name")

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().update(request, *args, **kwargs)


class EquipmentViewSet(LeasingPermissionMixin, MasterDataViewSet):
    view_permission = "leasing.view_equipment"
    queryset = Equipment.objects.select_related("category").all()
    serializer_class = EquipmentSerializer
    search_fields = ("code", "name", "serial_number", "identifier", "location")

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().update(request, *args, **kwargs)


class EquipmentRateViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_equipmentrate"
    queryset = EquipmentRate.objects.select_related("equipment").all()
    serializer_class = EquipmentRateSerializer
    search_fields = ("equipment__code", "equipment__name", "basis")

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.manage_equipment")
        return super().update(request, *args, **kwargs)


class RentalAgreementViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_rentalagreement"
    queryset = (
        RentalAgreement.objects.select_related("customer", "project", "requested_by", "approved_by")
        .prefetch_related("lines", "lines__equipment")
        .all()
    )
    serializer_class = RentalAgreementSerializer
    search_fields = ("number", "customer__legal_name", "project__code")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("status", "customer", "project"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.add_rentalagreement")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.change_rentalagreement")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=next_number("RA"),
            requested_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "leasing.change_rentalagreement")
        agreement = self.get_object()
        if agreement.status != RentalAgreement.Status.DRAFT:
            return error_response(
                "invalid_state",
                "Only a draft agreement can be submitted.",
                status.HTTP_409_CONFLICT,
            )
        agreement.status = RentalAgreement.Status.SUBMITTED
        agreement.submitted_at = timezone.now()
        agreement.updated_by = request.user
        agreement.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
        return Response(self.get_serializer(agreement).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "leasing.approve_rentalagreement")
        try:
            agreement = approve_agreement(self.get_object(), request.user)
        except LeasingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(agreement).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_equipment_action(self, request, pk=None):
        _require(request, "leasing.dispatch_rental")
        agreement = self.get_object()
        equipment = Equipment.objects.filter(pk=request.data.get("equipment")).first()
        if equipment is None:
            return error_response(
                "not_found", "Choose equipment on the agreement.", status.HTTP_404_NOT_FOUND
            )
        try:
            movement = dispatch_equipment(
                agreement,
                request.user,
                equipment=equipment,
                on_date=date.fromisoformat(
                    request.data.get("movement_date") or timezone.localdate().isoformat()
                ),
                condition=request.data.get("condition") or "good",
                expected_return=(
                    date.fromisoformat(request.data["expected_return_date"])
                    if request.data.get("expected_return_date")
                    else None
                ),
                notes=(request.data.get("notes") or "").strip(),
            )
        except (ValueError, LeasingConflict) as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        return Response(EquipmentMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def return_equipment(self, request, pk=None):
        _require(request, "leasing.return_equipment")
        agreement = self.get_object()
        equipment = Equipment.objects.filter(pk=request.data.get("equipment")).first()
        if equipment is None:
            return error_response(
                "not_found", "Choose equipment to return.", status.HTTP_404_NOT_FOUND
            )
        try:
            movement = return_equipment(
                agreement,
                request.user,
                equipment=equipment,
                on_date=date.fromisoformat(
                    request.data.get("movement_date") or timezone.localdate().isoformat()
                ),
                condition=request.data.get("condition") or "good",
                notes=(request.data.get("notes") or "").strip(),
            )
        except (ValueError, LeasingConflict) as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        return Response(EquipmentMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        _require(request, "leasing.close_rentalagreement")
        agreement = self.get_object()
        if agreement.status not in {RentalAgreement.Status.APPROVED, RentalAgreement.Status.ACTIVE}:
            return error_response(
                "invalid_state",
                "Only an approved or active agreement can be closed.",
                status.HTTP_409_CONFLICT,
            )
        movements = EquipmentMovement.objects.filter(agreement=agreement).order_by(
            "equipment_id", "-movement_date", "-id"
        )
        latest = {}
        for movement in movements:
            latest.setdefault(movement.equipment_id, movement)
        if any(m.kind == EquipmentMovement.Kind.DISPATCH for m in latest.values()):
            return error_response(
                "invalid_state",
                "Return all dispatched equipment before closing.",
                status.HTTP_409_CONFLICT,
            )
        agreement.status = RentalAgreement.Status.CLOSED
        agreement.closed_at = timezone.now()
        agreement.updated_by = request.user
        agreement.save(update_fields=["status", "closed_at", "updated_by", "updated_at"])
        create_audit_event(
            actor=request.user,
            action="rental_agreement.closed",
            entity_type="leasing.rentalagreement",
            entity_id=agreement.pk,
            after={"status": agreement.status},
            request=request,
        )
        return Response(self.get_serializer(agreement).data)


    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def attach(self, request, pk=None):
        _require(request, "leasing.change_rentalagreement")
        agreement = self.get_object()
        document, link = attach_upload(
            upload=request.FILES.get("file"),
            title=request.data.get("title", ""),
            entity_type=DocumentLink.EntityType.RENTAL_AGREEMENT,
            entity_id=agreement.pk,
            user=request.user,
            request=request,
        )
        return Response(
            {
                "id": link.pk,
                "document": document.pk,
                "title": document.title,
                "original_filename": document.original_filename,
                "download_path": f"/api/v1/documents/{document.pk}/download/",
            },
            status=status.HTTP_201_CREATED,
        )


class EquipmentReservationViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_equipmentreservation"
    queryset = EquipmentReservation.objects.select_related(
        "equipment", "customer", "agreement"
    ).all()
    serializer_class = EquipmentReservationSerializer
    search_fields = ("equipment__code", "customer__legal_name", "agreement__number")

    def get_queryset(self):
        queryset = super().get_queryset()
        equipment = self.request.query_params.get("equipment")
        if equipment:
            queryset = queryset.filter(equipment_id=equipment)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.add_equipmentreservation")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.change_equipmentreservation")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        _require(request, "leasing.change_equipmentreservation")
        reservation = self.get_object()
        if reservation.status != EquipmentReservation.Status.TENTATIVE:
            return error_response(
                "invalid_state",
                "Only a tentative reservation can be confirmed.",
                status.HTTP_409_CONFLICT,
            )
        try:
            check_availability(
                reservation.equipment,
                reservation.start_date,
                reservation.end_date,
                exclude_reservation=reservation,
            )
        except LeasingConflict as exc:
            return _conflict(exc)
        reservation.status = EquipmentReservation.Status.CONFIRMED
        reservation.updated_by = request.user
        reservation.save(update_fields=["status", "updated_by", "updated_at"])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, "leasing.change_equipmentreservation")
        reservation = self.get_object()
        if reservation.status in {
            EquipmentReservation.Status.CONVERTED,
            EquipmentReservation.Status.CANCELLED,
        }:
            return error_response(
                "invalid_state", "This reservation is already closed.", status.HTTP_409_CONFLICT
            )
        reservation.status = EquipmentReservation.Status.CANCELLED
        reservation.updated_by = request.user
        reservation.save(update_fields=["status", "updated_by", "updated_at"])
        return Response(self.get_serializer(reservation).data)


class EquipmentMovementViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_equipmentmovement"
    queryset = EquipmentMovement.objects.select_related("equipment", "agreement").all()
    serializer_class = EquipmentMovementSerializer
    search_fields = ("number", "equipment__code", "agreement__number")

    def create(self, request, *args, **kwargs):
        kind = request.data.get("kind")
        permission = (
            "leasing.dispatch_equipment"
            if kind == EquipmentMovement.Kind.DISPATCH
            else "leasing.return_equipment"
        )
        _require(request, permission)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agreement = serializer.validated_data.get("agreement")
        equipment = serializer.validated_data["equipment"]
        on_date = serializer.validated_data["movement_date"]
        try:
            if kind == EquipmentMovement.Kind.DISPATCH:
                if agreement is None:
                    return error_response(
                        "invalid_request",
                        "A dispatch needs an agreement.",
                        status.HTTP_400_BAD_REQUEST,
                    )
                movement = dispatch_equipment(
                    agreement,
                    request.user,
                    equipment=equipment,
                    on_date=on_date,
                    condition=serializer.validated_data.get("condition", "good"),
                    expected_return=serializer.validated_data.get("expected_return_date"),
                    notes=serializer.validated_data.get("notes", ""),
                )
            else:
                movement = return_equipment(
                    agreement,
                    request.user,
                    equipment=equipment,
                    on_date=on_date,
                    condition=serializer.validated_data.get("condition", "good"),
                    notes=serializer.validated_data.get("notes", ""),
                )
        except LeasingConflict as exc:
            return _conflict(exc)
        return Response(EquipmentMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return error_response(
            "method_not_allowed",
            "Equipment movements are append-only.",
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class EquipmentInspectionViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_equipmentinspection"
    queryset = EquipmentInspection.objects.select_related(
        "equipment", "agreement", "inspected_by"
    ).all()
    serializer_class = EquipmentInspectionSerializer
    search_fields = ("equipment__code", "agreement__number", "damage_description")

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.record_inspection")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(
            inspected_by=request.user,
            created_by=request.user,
            updated_by=request.user,
        )
        try:
            rental_inspection(record, request.user)
        except LeasingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.record_inspection")
        return super().update(request, *args, **kwargs)


class EquipmentMaintenanceViewSet(LeasingPermissionMixin, NoDeleteViewSet):
    view_permission = "leasing.view_equipmentmaintenance"
    queryset = EquipmentMaintenance.objects.select_related("equipment", "work_order").all()
    serializer_class = EquipmentMaintenanceSerializer
    search_fields = ("equipment__code", "description", "vendor")

    def create(self, request, *args, **kwargs):
        _require(request, "leasing.manage_maintenance")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "leasing.manage_maintenance")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        _require(request, "leasing.manage_maintenance")
        record = self.get_object()
        if record.status != EquipmentMaintenance.Status.PLANNED:
            return error_response(
                "invalid_state",
                "Only planned maintenance can be started.",
                status.HTTP_409_CONFLICT,
            )
        record.status = EquipmentMaintenance.Status.IN_PROGRESS
        record.equipment.status = Equipment.Status.MAINTENANCE
        record.equipment.updated_by = request.user
        record.equipment.save(update_fields=["status", "updated_by", "updated_at"])
        record.updated_by = request.user
        record.save(update_fields=["status", "updated_by", "updated_at"])
        return Response(self.get_serializer(record).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        _require(request, "leasing.manage_maintenance")
        try:
            record = complete_maintenance(self.get_object(), request.user)
        except LeasingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(record).data)


class EquipmentUtilisationView(APIView):
    def get(self, request):
        _require(request, "leasing.view_equipment")
        start, end = _dates(request)
        return _paged(request, utilisation_rows(start, end))


class EquipmentWarningsView(APIView):
    def get(self, request):
        _require(request, "leasing.view_equipment")
        return _paged(request, warning_rows())


class EquipmentAvailabilityView(APIView):
    def get(self, request):
        _require(request, "leasing.view_equipment")
        start, end = _dates(request)
        return _paged(request, availability_rows(start, end))
