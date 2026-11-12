from __future__ import annotations

import logging
from pathlib import Path

from django.http import FileResponse
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.core.models import create_audit_event
from apps.documents.models import Document, DocumentCategory, DocumentLink
from apps.documents.serializers import (
    DocumentCategorySerializer,
    DocumentLinkSerializer,
    DocumentSerializer,
)
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet

logger = logging.getLogger(__name__)


def _require(user, permission: str) -> None:
    if not user.has_perm(permission):
        raise PermissionDenied("You do not have permission to perform this action.")


class DocumentCategoryViewSet(MasterDataViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    search_fields = ("code", "name")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            _require(request.user, "documents.view_documentcategory")
        else:
            _require(
                request.user,
                "documents.add_documentcategory"
                if request.method == "POST"
                else "documents.change_documentcategory",
            )


class DocumentViewSet(NoDeleteViewSet):
    queryset = Document.objects.select_related("category").all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            _require(request.user, "documents.view_document")
        else:
            _require(
                request.user,
                "documents.add_document"
                if request.method == "POST"
                else "documents.change_document",
            )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        # Download is authenticated by the API default and recorded here; the
        # append-only audit trail (W7) will replace this log call.
        logger.info(
            "document.download",
            extra={"document_id": document.pk, "user_id": request.user.pk},
        )
        create_audit_event(
            actor=request.user,
            action="document.downloaded",
            entity_type="documents.document",
            entity_id=document.pk,
            after={"filename": document.original_filename},
            request=request,
        )
        filename = document.original_filename or Path(document.file.name).name
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=filename,
        )
        response["Content-Type"] = document.mime_type or "application/octet-stream"
        return response


class DocumentLinkViewSet(NoDeleteViewSet):
    queryset = DocumentLink.objects.select_related("document").all()
    serializer_class = DocumentLinkSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            _require(request.user, "documents.view_documentlink")
        else:
            _require(
                request.user,
                "documents.add_documentlink"
                if request.method == "POST"
                else "documents.change_documentlink",
            )
