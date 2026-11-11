from __future__ import annotations

import logging
from pathlib import Path

from django.http import FileResponse
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.documents.models import Document, DocumentCategory, DocumentLink
from apps.documents.serializers import (
    DocumentCategorySerializer,
    DocumentLinkSerializer,
    DocumentSerializer,
)
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet

logger = logging.getLogger(__name__)


class DocumentCategoryViewSet(MasterDataViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    search_fields = ("code", "name")


class DocumentViewSet(NoDeleteViewSet):
    queryset = Document.objects.select_related("category").all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        # Download is authenticated by the API default and recorded here; the
        # append-only audit trail (W7) will replace this log call.
        logger.info(
            "document.download",
            extra={"document_id": document.pk, "user_id": request.user.pk},
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
