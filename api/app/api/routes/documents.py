"""API route endpoints for Document uploads (PDF ingestion)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.source import SourceResponse
from app.services import pdf as pdf_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a text PDF document",
)
async def upload_document_endpoint(
    file: UploadFile = File(..., description="Selectable text PDF file"),
    db: Session = Depends(get_db),
) -> SourceResponse:
    """Validate, extract text page-by-page, and store a PDF document."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename is missing from upload.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read uploaded file stream: {str(exc)}",
        )

    source = pdf_service.save_pdf_document(
        db=db,
        file_bytes=file_bytes,
        original_filename=file.filename,
    )

    return SourceResponse(
        id=source.id,
        kind=source.kind,
        title=source.title,
        content=source.content,
        original_filename=source.original_filename,
        mime_type=source.mime_type,
        size_bytes=source.size_bytes,
        content_sha256=source.content_sha256,
        status=source.status,
        error_message=source.error_message,
        tags=[tag.name for tag in source.tags],
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
