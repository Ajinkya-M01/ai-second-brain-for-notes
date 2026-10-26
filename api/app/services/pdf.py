"""PDF validation, page-by-page text extraction, and storage service using pypdf."""

import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from fastapi import HTTPException, status
import pypdf
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import Chunk, Source
from app.services.chunking import create_chunks_for_pdf_pages


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted text whitespace while preserving paragraph structure."""
    if not text:
        return ""
    # Standardize line breaks
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse horizontal spaces/tabs to a single space
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    # Collapse 3 or more consecutive newlines into 2 (paragraph break)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def validate_and_extract_pdf(
    file_bytes: bytes, filename: str
) -> Tuple[List[Dict[str, Any]], str]:
    """Validate PDF file size, signature, encryption, page cap, and extract text page by page.

    Returns:
        Tuple of (pages_list, concatenated_text)
    Raises:
        HTTPException with appropriate 413, 415, or 422 status codes.
    """
    # 1. Empty file check
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty (0 bytes).",
        )

    # 2. Maximum file size check (413 Payload Too Large)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({len(file_bytes) / (1024 * 1024):.1f} MB) exceeds maximum allowed upload cap of {settings.MAX_UPLOAD_MB} MB.",
        )

    # 3. File extension check (415 Unsupported Media Type)
    clean_filename = Path(filename).name
    if not clean_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension '{Path(filename).suffix}'. Only .pdf files are supported.",
        )

    # 4. File signature / Magic bytes check (%PDF)
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid file signature: file does not have a valid %PDF header.",
        )

    # 5. Parse with pypdf
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Corrupt or unreadable PDF document: {str(exc)}",
        )

    # 6. Encrypted PDF check
    if reader.is_encrypted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Encrypted or password-protected PDFs are not supported.",
        )

    # 7. Page count checks
    num_pages = len(reader.pages)
    if num_pages == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF document contains 0 pages.",
        )

    if num_pages > settings.MAX_PDF_PAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF page count ({num_pages}) exceeds the limit of {settings.MAX_PDF_PAGES} pages.",
        )

    # 8. Extract text page-by-page preserving 1-based page numbers
    pages: List[Dict[str, Any]] = []
    total_extracted_chunks: List[str] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:
            raw_text = ""

        cleaned_text = normalize_extracted_text(raw_text)
        if cleaned_text:
            total_extracted_chunks.append(cleaned_text)

        pages.append({
            "page_number": page_idx,
            "text": cleaned_text,
        })

    # 9. Scanned / image-only PDF check (empty extractable text)
    concatenated_text = " ".join(total_extracted_chunks).strip()
    if not concatenated_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text found in PDF. This document appears to be scanned or contains only images. OCR is not supported in the MVP.",
        )

    return pages, concatenated_text


def save_pdf_document(
    db: Session,
    file_bytes: bytes,
    original_filename: str,
) -> Source:
    """Validate, extract, save PDF on disk with a server-generated UUID, and persist in SQLite."""
    # Validate and extract pages
    pages, _ = validate_and_extract_pdf(file_bytes, original_filename)

    source_id = str(uuid.uuid4())
    content_sha256 = hashlib.sha256(file_bytes).hexdigest()
    size_bytes = len(file_bytes)

    # Ensure upload directory exists
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Store PDF on disk under server-generated UUID filename only
    server_filename = f"{source_id}.pdf"
    disk_path = upload_dir / server_filename
    disk_path.write_bytes(file_bytes)

    # Clean display title derived from original filename
    base_title = Path(original_filename).stem.replace("_", " ").replace("-", " ").strip()
    title = base_title if base_title else "Uploaded PDF Document"

    # Assemble canonical content formatted with page markers
    combined_content = "\n\n".join(
        f"--- Page {p['page_number']} ---\n{p['text']}"
        for p in pages
        if p["text"]
    )

    source = Source(
        id=source_id,
        kind="pdf",
        title=title,
        content=combined_content,
        original_filename=Path(original_filename).name,
        mime_type="application/pdf",
        size_bytes=size_bytes,
        content_sha256=content_sha256,
        status="indexed",  # Mark indexed since text extraction succeeded
        error_message=None,
    )
    db.add(source)

    # Persist page-aware chunks with preserved 1-based page numbers and deterministic IDs
    chunks = create_chunks_for_pdf_pages(source_id, pages)
    db.add_all(chunks)

    db.commit()
    db.refresh(source)
    return source
