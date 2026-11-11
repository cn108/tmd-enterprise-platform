from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    RfqSupplier,
    SupplierQuote,
    SupplierSelection,
)
from apps.procurement.serializers import (
    DeliveryScheduleSerializer,
    DestinationSerializer,
    GoodsReceiptCreateSerializer,
    GoodsReceiptNoteSerializer,
    PurchaseOrderSerializer,
    PurchaseRequestSerializer,
    RequestForQuotationSerializer,
    RfqSupplierSerializer,
    SupplierQuoteSerializer,
    SupplierSelectionSerializer,
)
from apps.procurement.services import (
    StateConflict,
    approve_order,
    approve_request,
    close_order,
    issue_order,
    issue_rfq,
    receive_goods,
    reject_request,
    submit_order,
    submit_request,
)
from shared.exceptions import error_response
from shared.viewsets import NoDeleteViewSet

APPROVE_REQUEST = "procurement.approve_purchaserequest"
APPROVE_ORDER = "procurement.approve_purchaseorder"
SELECT_SUPPLIER = "procurement.select_supplier"


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: StateConflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


class DestinationViewSet(NoDeleteViewSet):
    queryset = Destination.objects.select_related("project", "warehouse").all()
    serializer_class = DestinationSerializer


class PurchaseRequestViewSet(NoDeleteViewSet):
    queryset = PurchaseRequest.objects.select_related(
        "requester", "department", "destination"
    ).prefetch_related("lines")
    serializer_class = PurchaseRequestSerializer

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        try:
            return Response(PurchaseRequestSerializer(submit_request(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, APPROVE_REQUEST)
        try:
            result = approve_request(self.get_object(), request.user)
        except StateConflict as exc:
            return _conflict(exc)
        return Response(PurchaseRequestSerializer(result).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, APPROVE_REQUEST)
        reason = (request.data.get("reason") or "").strip()
        try:
            result = reject_request(self.get_object(), request.user, reason)
        except StateConflict as exc:
            return _conflict(exc)
        return Response(PurchaseRequestSerializer(result).data)


class RequestForQuotationViewSet(NoDeleteViewSet):
    queryset = RequestForQuotation.objects.select_related("request").prefetch_related("invitations")
    serializer_class = RequestForQuotationSerializer

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        try:
            return Response(RequestForQuotationSerializer(issue_rfq(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)


class RfqSupplierViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = RfqSupplier.objects.select_related("rfq", "supplier").all()
    serializer_class = RfqSupplierSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class SupplierQuoteViewSet(NoDeleteViewSet):
    queryset = SupplierQuote.objects.select_related("rfq", "supplier").prefetch_related("lines")
    serializer_class = SupplierQuoteSerializer


class SupplierSelectionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SupplierSelection.objects.select_related("rfq", "quote").all()
    serializer_class = SupplierSelectionSerializer

    def create(self, request, *args, **kwargs):
        _require(request, SELECT_SUPPLIER)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class PurchaseOrderViewSet(NoDeleteViewSet):
    queryset = PurchaseOrder.objects.select_related(
        "supplier", "request", "destination"
    ).prefetch_related("lines")
    serializer_class = PurchaseOrderSerializer

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        try:
            return Response(PurchaseOrderSerializer(submit_order(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, APPROVE_ORDER)
        try:
            result = approve_order(self.get_object(), request.user)
        except StateConflict as exc:
            return _conflict(exc)
        return Response(PurchaseOrderSerializer(result).data)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        try:
            return Response(PurchaseOrderSerializer(issue_order(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        reason = (request.data.get("reason") or "").strip()
        try:
            result = close_order(self.get_object(), request.user, reason)
        except StateConflict as exc:
            return _conflict(exc)
        return Response(PurchaseOrderSerializer(result).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = self.get_object()
        payload = GoodsReceiptCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            receipt = receive_goods(
                order,
                request.user,
                payload.validated_data["received_at"],
                payload.validated_data["lines"],
                payload.validated_data.get("notes", ""),
            )
        except StateConflict as exc:
            return _conflict(exc)
        return Response(GoodsReceiptNoteSerializer(receipt).data, status=status.HTTP_201_CREATED)


class DeliveryScheduleViewSet(NoDeleteViewSet):
    queryset = DeliverySchedule.objects.select_related("order_line", "destination").all()
    serializer_class = DeliveryScheduleSerializer


class GoodsReceiptNoteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GoodsReceiptNote.objects.select_related("order", "received_by").prefetch_related(
        "lines"
    )
    serializer_class = GoodsReceiptNoteSerializer
