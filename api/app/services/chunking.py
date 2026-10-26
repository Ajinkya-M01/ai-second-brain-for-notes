"""Text chunking service for notes and PDF documents.

Provides page-aware, deterministic chunking with paragraph/sentence boundary
respect, configurable token size and overlap, and stable RFC 4122 UUIDs.
"""

import re
import uuid
from typing import Any, Dict, List, Optional
from app.db.models import Chunk


# Standard defaults matching blueprint specifications (Section 7: 700-900 tokens, 100-150 overlap)
DEFAULT_CHUNK_SIZE_TOKENS = 800
DEFAULT_CHUNK_OVERLAP_TOKENS = 120

# Namespace for deterministic UUIDv5 chunk generation
CHUNK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:ai-second-brain:chunks")


def estimate_tokens(text: str) -> int:
    """Estimate token count using the standard ~4 chars per token rule of thumb.

    For typical English / code text, 1 token is approximately 4 characters (or ~0.75 words).
    This heuristic is fast, deterministic, and avoids external tokenizer dependencies.
    """
    if not text or not text.strip():
        return 0
    clean = text.strip()
    return max(1, len(clean) // 4)


def generate_chunk_id(source_id: str, ordinal: int) -> str:
    """Generate a deterministic, stable UUIDv5 string for a chunk.

    Given the same source_id and ordinal, this function will ALWAYS return
    the exact same 36-character UUID string. This enables idempotent re-indexing,
    stable citations, and consistent vector store upserts.
    """
    name = f"source:{source_id}:ordinal:{ordinal}"
    return str(uuid.uuid5(CHUNK_NAMESPACE, name))


def _split_into_units(text: str, max_tokens: int) -> List[str]:
    """Hierarchically split text into semantic units (paragraphs, sentences, words).

    Each returned unit will have estimate_tokens(unit) <= max_tokens.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if estimate_tokens(cleaned) <= max_tokens:
        return [cleaned]

    # 1. Try splitting by paragraph (double newline)
    if "\n\n" in cleaned:
        parts = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        if len(parts) > 1:
            units: List[str] = []
            for p in parts:
                units.extend(_split_into_units(p, max_tokens))
            return units

    # 2. Try splitting by single newline
    if "\n" in cleaned:
        parts = [p.strip() for p in cleaned.split("\n") if p.strip()]
        if len(parts) > 1:
            units: List[str] = []
            for p in parts:
                units.extend(_split_into_units(p, max_tokens))
            return units

    # 3. Try splitting by sentence boundary (. ? ! followed by space)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    if len(sentences) > 1:
        units: List[str] = []
        for s in sentences:
            units.extend(_split_into_units(s, max_tokens))
        return units

    # 4. Try splitting by clause or punctuation (, ; :)
    clauses = [c.strip() for c in re.split(r"(?<=[,;:])\s+", cleaned) if c.strip()]
    if len(clauses) > 1:
        units: List[str] = []
        for c in clauses:
            units.extend(_split_into_units(c, max_tokens))
        return units

    # 5. Try splitting by word (space)
    words = [w for w in cleaned.split(" ") if w]
    if len(words) > 1:
        units: List[str] = []
        for w in words:
            units.extend(_split_into_units(w, max_tokens))
        return units

    # 6. Fallback for arbitrarily long continuous strings (e.g. huge hex or URL)
    char_step = max(1, max_tokens * 4)
    return [cleaned[i : i + char_step] for i in range(0, len(cleaned), char_step)]


def chunk_text(
    text: str,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[str]:
    """Chunk text into segments of ~chunk_size_tokens with ~chunk_overlap_tokens overlap.

    Respects natural paragraph and sentence boundaries.
    """
    if not text or not text.strip():
        return []

    cleaned = text.strip()
    if estimate_tokens(cleaned) <= chunk_size_tokens:
        return [cleaned]

    # Ensure valid parameters
    chunk_size_tokens = max(10, chunk_size_tokens)
    chunk_overlap_tokens = max(0, min(chunk_overlap_tokens, chunk_size_tokens - 1))

    # Split into units small enough to fit within chunk_size_tokens
    units = _split_into_units(cleaned, max_tokens=chunk_size_tokens)
    if not units:
        return []
    if len(units) == 1:
        return units

    chunks: List[str] = []
    i = 0
    n = len(units)

    while i < n:
        current_units: List[str] = []
        current_tokens = 0

        # Greedily pack units until reaching chunk_size_tokens
        j = i
        while j < n:
            unit = units[j]
            unit_tokens = estimate_tokens(unit)
            if current_units and (current_tokens + unit_tokens > chunk_size_tokens):
                break
            current_units.append(unit)
            current_tokens += unit_tokens
            j += 1

        # Join units using spaces
        chunk_str = " ".join(current_units).strip()
        if chunk_str:
            chunks.append(chunk_str)

        # If we reached the end, stop
        if j >= n:
            break

        # Calculate overlap for next chunk:
        # Walk backwards from j-1 to accumulate ~chunk_overlap_tokens
        if chunk_overlap_tokens > 0:
            overlap_accum = 0
            next_start = j
            back_idx = j - 1
            while back_idx >= i:
                u_tok = estimate_tokens(units[back_idx])
                if overlap_accum + u_tok > chunk_overlap_tokens and overlap_accum > 0:
                    break
                overlap_accum += u_tok
                next_start = back_idx
                back_idx -= 1

            # Ensure forward progress
            if next_start <= i:
                next_start = i + 1
            i = next_start
        else:
            i = j

    return chunks


def create_chunks_for_note(
    source_id: str,
    content: Optional[str],
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[Chunk]:
    """Create chunk records for a note source.

    Notes have no page numbers, so page_number is None.
    Chunk IDs are deterministic based on source_id and ordinal.
    """
    if not content or not content.strip():
        return []

    text_chunks = chunk_text(
        content,
        chunk_size_tokens=chunk_size_tokens,
        chunk_overlap_tokens=chunk_overlap_tokens,
    )

    chunks: List[Chunk] = []
    for ordinal, chunk_text_str in enumerate(text_chunks):
        chunk_id = generate_chunk_id(source_id, ordinal)
        chunks.append(
            Chunk(
                id=chunk_id,
                source_id=source_id,
                ordinal=ordinal,
                page_number=None,
                text=chunk_text_str,
                token_estimate=estimate_tokens(chunk_text_str),
            )
        )
    return chunks


def create_chunks_for_pdf_pages(
    source_id: str,
    pages: List[Dict[str, Any]],
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[Chunk]:
    """Create page-aware chunk records for a PDF source.

    Each page is chunked independently to preserve precise 1-based page numbers.
    Empty/blank pages produce no chunks.
    Ordinals increment sequentially (0, 1, 2, ...) across all pages.
    Chunk IDs are deterministic based on source_id and ordinal.
    """
    chunks: List[Chunk] = []
    current_ordinal = 0

    for page in pages:
        page_number = page.get("page_number")
        page_text = page.get("text", "").strip()

        if not page_text:
            continue

        page_chunks = chunk_text(
            page_text,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
        )

        for chunk_text_str in page_chunks:
            chunk_id = generate_chunk_id(source_id, current_ordinal)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    source_id=source_id,
                    ordinal=current_ordinal,
                    page_number=page_number,
                    text=chunk_text_str,
                    token_estimate=estimate_tokens(chunk_text_str),
                )
            )
            current_ordinal += 1

    return chunks
