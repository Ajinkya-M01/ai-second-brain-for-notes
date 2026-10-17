"""Tests for PDF upload, validation, extraction, chunking, and disk cleanup."""

import io
from pathlib import Path
import pypdf
from app.core.config import settings

SAMPLE_TEXT_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 58 >>
stream
BT /F1 12 Tf 100 700 Td (Attention Is All You Need Paper) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000246 00000 n 
0000000354 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
432
%%EOF"""


def make_encrypted_pdf() -> bytes:
    writer = pypdf.PdfWriter()
    writer.append(io.BytesIO(SAMPLE_TEXT_PDF))
    writer.encrypt("topsecret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_blank_pdf(num_pages: int = 1) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_valid_text_pdf_upload(client):
    """Verify uploading a valid selectable text PDF creates source, chunks, and disk file."""
    response = client.post(
        "/api/v1/documents",
        files={"file": ("attention_is_all_you_need.pdf", SAMPLE_TEXT_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["kind"] == "pdf"
    assert data["status"] == "indexed"
    assert data["original_filename"] == "attention_is_all_you_need.pdf"
    assert "Attention Is All You Need Paper" in data["content"]
    assert data["size_bytes"] == len(SAMPLE_TEXT_PDF)

    # Verify disk file exists under server-generated UUID (never user filename)
    source_id = data["id"]
    disk_file = Path(settings.UPLOAD_DIR) / f"{source_id}.pdf"
    assert disk_file.exists()

    # Verify chunks endpoint returns the extracted page chunk with 1-based page number
    chunk_res = client.get(f"/api/v1/sources/{source_id}/chunks")
    assert chunk_res.status_code == 200
    chunk_data = chunk_res.json()
    assert chunk_data["total"] >= 1
    assert chunk_data["items"][0]["page_number"] == 1
    assert "Attention Is All You Need Paper" in chunk_data["items"][0]["text"]

    # Verify generic /api/v1/sources lists the PDF
    sources_res = client.get("/api/v1/sources?kind=pdf")
    assert sources_res.status_code == 200
    assert any(s["id"] == source_id for s in sources_res.json()["items"])

    # Clean up disk file
    client.delete(f"/api/v1/sources/{source_id}")
    assert not disk_file.exists()


def test_reject_wrong_extension(client):
    """Verify rejection of non-PDF file extension with 415."""
    response = client.post(
        "/api/v1/documents",
        files={"file": ("report.docx", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert response.status_code == 415
    assert "extension" in response.json()["detail"].lower()


def test_reject_invalid_magic_bytes(client):
    """Verify rejection of file without %PDF signature with 415."""
    response = client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"NOT_A_REAL_PDF_DATA", "application/pdf")},
    )
    assert response.status_code == 415
    assert "signature" in response.json()["detail"].lower()


def test_reject_empty_pdf(client):
    """Verify rejection of 0-byte upload with 422."""
    response = client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_reject_encrypted_pdf(client):
    """Verify rejection of password-protected PDF with 422."""
    encrypted_bytes = make_encrypted_pdf()
    response = client.post(
        "/api/v1/documents",
        files={"file": ("encrypted.pdf", encrypted_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert "encrypted" in response.json()["detail"].lower()


def test_reject_page_count_exceeded(client):
    """Verify rejection of PDF exceeding MAX_PDF_PAGES with 422."""
    many_pages_bytes = make_blank_pdf(num_pages=settings.MAX_PDF_PAGES + 2)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("huge_pages.pdf", many_pages_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert "page count" in response.json()["detail"].lower()


def test_reject_scanned_image_only_pdf(client):
    """Verify rejection of scanned/empty-text PDF with informative OCR message."""
    scanned_pdf_bytes = make_blank_pdf(num_pages=2)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("scanned_document.pdf", scanned_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "scanned" in detail.lower()
    assert "ocr is not supported" in detail.lower()


def test_reject_oversized_file(client, monkeypatch):
    """Verify rejection of file exceeding upload size limit with 413."""
    # Temporarily set MAX_UPLOAD_MB to a tiny limit (e.g. 0.0001 MB = ~100 bytes)
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0.0001)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("large.pdf", SAMPLE_TEXT_PDF, "application/pdf")},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"].lower()
