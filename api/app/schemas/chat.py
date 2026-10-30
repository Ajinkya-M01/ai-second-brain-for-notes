"""Pydantic schemas for grounded chat and question-answering."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Verified citation metadata built directly from retrieved backend chunks."""

    label: str = Field(..., description="Citation marker such as [S1]")
    chunk_id: str = Field(..., description="Unique chunk UUID")
    source_id: str = Field(..., description="Parent source document UUID")
    title: str = Field(..., description="Source title or filename")
    page_number: Optional[int] = Field(None, description="1-based page number for PDFs, or None for notes")
    excerpt: str = Field(..., description="Relevant text snippet used as evidence")


class ChatRequest(BaseModel):
    """User question and optional retrieval filtering options."""

    question: str = Field(..., min_length=1, max_length=1000, description="The user's question")
    source_ids: Optional[List[str]] = Field(None, description="Optional list of source IDs to constrain retrieval")
    limit: int = Field(5, ge=1, le=10, description="Maximum number of context chunks to retrieve")
    min_similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Custom similarity threshold override")
    conversation_id: Optional[str] = Field(None, description="Optional conversation identifier")


class ChatResponse(BaseModel):
    """Grounded question-answering response with verified citations."""

    question: str
    answer: str
    citations: List[Citation]
    grounded: bool = Field(..., description="True if answered from retrieved evidence, False if no evidence was found")
    model_id: Optional[str] = None
    retrieved_chunks_count: int = 0
    conversation_id: Optional[str] = None

