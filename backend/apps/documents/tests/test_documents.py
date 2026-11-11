from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Document

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def upload(client, name: str = "contract.pdf", content: bytes = PDF, **extra):
    file = SimpleUploadedFile(name, content, content_type="application/pdf")
    return client.post(
        "/api/v1/documents/", {"title": "Contract", "file": file, **extra}, format="multipart"
    )


def test_upload_records_checksum_and_metadata(auth_client):
    response = upload(auth_client)

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["original_filename"] == "contract.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert len(body["checksum_sha256"]) == 64
    assert "file" not in body


def test_oversized_upload_is_refused(auth_client, settings):
    settings.DOCUMENT_MAX_UPLOAD_BYTES = 10

    response = upload(auth_client, content=b"x" * 50)

    assert response.status_code == 400


def test_disallowed_extension_is_refused(auth_client):
    file = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/octet-stream")

    response = auth_client.post(
        "/api/v1/documents/", {"title": "Bad", "file": file}, format="multipart"
    )

    assert response.status_code == 400


def test_download_requires_authentication_and_streams_the_file(auth_client, api_client):
    document_id = upload(auth_client).json()["id"]
    url = f"/api/v1/documents/{document_id}/download/"

    assert api_client.get(url).status_code == 401

    response = auth_client.get(url)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF
    assert "attachment" in response["Content-Disposition"]


def test_media_url_is_not_routed(auth_client):
    document = Document.objects.get(pk=upload(auth_client).json()["id"])

    response = auth_client.get(f"/media/{document.file.name}")

    assert response.status_code == 404


def test_document_bytes_cannot_be_replaced_on_update(auth_client):
    document_id = upload(auth_client).json()["id"]
    original = Document.objects.get(pk=document_id)

    replacement = SimpleUploadedFile("new.pdf", b"REPLACED", content_type="application/pdf")
    response = auth_client.patch(
        f"/api/v1/documents/{document_id}/",
        {"title": "Renamed", "file": replacement},
        format="multipart",
    )

    assert response.status_code == 200, response.content
    original.refresh_from_db()
    assert original.title == "Renamed"
    assert original.checksum_sha256 != ""
    assert original.size_bytes == len(PDF)
    assert original.original_filename == "contract.pdf"


def test_document_link_is_unique(auth_client):
    document_id = upload(auth_client).json()["id"]
    payload = {"document": document_id, "entity_type": "supplier", "entity_id": 1}

    assert auth_client.post("/api/v1/document-links/", payload, format="json").status_code == 201
    assert auth_client.post("/api/v1/document-links/", payload, format="json").status_code == 400


def test_documents_are_not_deleted(auth_client):
    document_id = upload(auth_client).json()["id"]

    response = auth_client.delete(f"/api/v1/documents/{document_id}/")

    assert response.status_code == 409
    assert Document.objects.filter(pk=document_id).exists()
