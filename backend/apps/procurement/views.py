from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RfqSupplier,
    SupplierQuote,
    SupplierSelection,
)
from apps.procurement.serializers import (
    DeliveryScheduleSerializer,
    DestinationSerializer,
    GoodsReceiptCreateSerializer,
    GoodsReceiptLineReadSerializer,
    GoodsReceiptNoteSerializer,
    PurchaseOrderLineSerializer,
    PurchaseOrderSerializer,
    PurchaseRequestLineSerializer,
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


class ProcurementViewPermissionMixin:
    view_permission = ""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS and self.view_permission:
            _require(request, self.view_permission)


class DestinationViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_destination"
    queryset = Destination.objects.select_related("project", "warehouse").all()
    serializer_class = DestinationSerializer


class PurchaseRequestLineViewSet(ProcurementViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Lines of a request, for quotation entry. Filter with ``?request=``."""

    view_permission = "procurement.view_purchaserequestline"
    serializer_class = PurchaseRequestLineSerializer

    def get_queryset(self):
        queryset = PurchaseRequestLine.objects.select_related("item", "uom", "cost_centre")
        request_id = (self.request.query_params.get("request") or "").strip()
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        return queryset


class PurchaseOrderLineViewSet(ProcurementViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Lines of an order, for delivery scheduling. Filter with ``?order=``."""

    view_permission = "procurement.view_purchaseorderline"
    serializer_class = PurchaseOrderLineSerializer

    def get_queryset(self):
        queryset = PurchaseOrderLine.objects.select_related("item", "uom", "cost_centre")
        order_id = (self.request.query_params.get("order") or "").strip()
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset


class PurchaseRequestViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_purchaserequest"
    queryset = PurchaseRequest.objects.select_related(
        "requester", "department", "destination"
    ).prefetch_related("lines")
    serializer_class = PurchaseRequestSerializer
    search_fields = ("number", "justification", "requester__email", "destination__location_name")
    ordering_fields = ("number", "status", "required_by", "created_at", "submitted_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        status = (self.request.query_params.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "procurement.add_purchaserequest")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "procurement.change_purchaserequest")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "procurement.add_purchaserequest")
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


class RequestForQuotationViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_requestforquotation"
    queryset = RequestForQuotation.objects.select_related("request").prefetch_related("invitations")
    serializer_class = RequestForQuotationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "procurement.add_requestforquotation")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "procurement.change_requestforquotation")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        _require(request, "procurement.add_requestforquotation")
        try:
            return Response(RequestForQuotationSerializer(issue_rfq(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)


class RfqSupplierViewSet(
    ProcurementViewPermissionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    view_permission = "procurement.view_rfqsupplier"
    queryset = RfqSupplier.objects.select_related("rfq", "supplier").all()
    serializer_class = RfqSupplierSerializer

    def perform_create(self, serializer):
        _require(self.request, "procurement.add_rfqsupplier")
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class SupplierQuoteViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_supplierquote"
    queryset = SupplierQuote.objects.select_related("rfq", "supplier").prefetch_related("lines")
    serializer_class = SupplierQuoteSerializer

    def create(self, request, *args, **kwargs):
        _require(request, "procurement.add_supplierquote")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "procurement.change_supplierquote")
        return super().update(request, *args, **kwargs)


class SupplierSelectionViewSet(
    ProcurementViewPermissionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    view_permission = "procurement.view_supplierselection"
    queryset = SupplierSelection.objects.select_related("rfq", "quote").all()
    serializer_class = SupplierSelectionSerializer

    def create(self, request, *args, **kwargs):
        _require(request, SELECT_SUPPLIER)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class PurchaseOrderViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_purchaseorder"
    queryset = PurchaseOrder.objects.select_related(
        "supplier", "request", "destination"
    ).prefetch_related("lines__schedules")
    serializer_class = PurchaseOrderSerializer
    search_fields = ("number", "supplier__legal_name", "request__number")
    ordering_fields = ("number", "status", "created_at", "submitted_at", "issued_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        status = (self.request.query_params.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "procurement.add_purchaseorder")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "procurement.change_purchaseorder")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "procurement.change_purchaseorder")
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
        _require(request, "procurement.change_purchaseorder")
        try:
            return Response(PurchaseOrderSerializer(issue_order(self.get_object())).data)
        except StateConflict as exc:
            return _conflict(exc)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        _require(request, "procurement.change_purchaseorder")
        reason = (request.data.get("reason") or "").strip()
        try:
            result = close_order(self.get_object(), request.user, reason)
        except StateConflict as exc:
            return _conflict(exc)
        return Response(PurchaseOrderSerializer(result).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        _require(request, "procurement.add_goodsreceiptnote")
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


class DeliveryScheduleViewSet(ProcurementViewPermissionMixin, NoDeleteViewSet):
    view_permission = "procurement.view_deliveryschedule"
    queryset = DeliverySchedule.objects.select_related("order_line", "destination").all()
    serializer_class = DeliveryScheduleSerializer


class GoodsReceiptNoteViewSet(ProcurementViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "procurement.view_goodsreceiptnote"
    queryset = GoodsReceiptNote.objects.select_related("order", "received_by").prefetch_related(
        "lines"
    )
    serializer_class = GoodsReceiptNoteSerializer
    search_fields = ("number", "order__number")
    ordering_fields = ("number", "received_at", "created_at")


class GoodsReceiptLineViewSet(ProcurementViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Accepted receipt lines available for supplier-invoice matching."""

    view_permission = "procurement.view_goodsreceiptline"
    serializer_class = GoodsReceiptLineReadSerializer

    def get_queryset(self):
        queryset = GoodsReceiptLine.objects.select_related("receipt", "order_line", "schedule")
        receipt = (self.request.query_params.get("receipt") or "").strip()
        order = (self.request.query_params.get("order") or "").strip()
        order_line = (self.request.query_params.get("order_line") or "").strip()
        if receipt:
            queryset = queryset.filter(receipt_id=receipt)
        if order:
            queryset = queryset.filter(receipt__order_id=order)
        if order_line:
            queryset = queryset.filter(order_line_id=order_line)
        return queryset
