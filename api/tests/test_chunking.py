"""Tests for page-aware text chunking, boundaries, overlap, stable IDs, and page references."""

import io
import uuid
import pypdf
from app.db.models import Chunk, Source
from app.services.chunking import (
    DEFAULT_CHUNK_OVERLAP_TOKENS,
    DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_text,
    create_chunks_for_note,
    create_chunks_for_pdf_pages,
    estimate_tokens,
    generate_chunk_id,
)


def test_estimate_tokens():
    """Verify token estimation heuristic (~4 chars/token)."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0
    assert estimate_tokens("Hello") == 1  # 5 chars -> 1 token
    assert estimate_tokens("A" * 40) == 10  # 40 chars -> 10 tokens
    assert estimate_tokens("This is a standard sentence for testing.") >= 5


def test_stable_deterministic_chunk_ids():
    """Verify chunk IDs are valid UUIDs, stable across repeated calls, and unique per source/ordinal."""
    source_id_1 = "d3b07384-d113-4670-a352-8714e861d810"
    source_id_2 = "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"

    # Stable across calls
    id_1_0_a = generate_chunk_id(source_id_1, 0)
    id_1_0_b = generate_chunk_id(source_id_1, 0)
    assert id_1_0_a == id_1_0_b
    assert len(id_1_0_a) == 36
    # Valid UUID format
    parsed_uuid = uuid.UUID(id_1_0_a)
    assert parsed_uuid.version == 5

    # Distinct ordinals produce distinct IDs
    id_1_1 = generate_chunk_id(source_id_1, 1)
    assert id_1_0_a != id_1_1

    # Distinct source IDs produce distinct IDs even with same ordinal
    id_2_0 = generate_chunk_id(source_id_2, 0)
    assert id_1_0_a != id_2_0


def test_chunk_boundaries_paragraphs():
    """Verify chunking splits along paragraph boundaries when content exceeds chunk size."""
    p1 = "Paragraph 1 is about architecture principles and modular software design."
    p2 = "Paragraph 2 details database transactions and foreign key cascade semantics."
    p3 = "Paragraph 3 discusses vector embeddings and nearest neighbor similarity queries."
    text = f"{p1}\n\n{p2}\n\n{p3}"

    # Use a small chunk size so each paragraph forms a distinct chunk
    chunks = chunk_text(text, chunk_size_tokens=25, chunk_overlap_tokens=0)
    assert len(chunks) == 3
    assert p1 in chunks[0]
    assert p2 in chunks[1]
    assert p3 in chunks[2]


def test_chunk_boundaries_sentences():
    """Verify chunking splits along sentence boundaries within a single dense paragraph."""
    s1 = "Neural networks rely on backpropagation to compute parameter gradients."
    s2 = "Attention mechanisms enable direct interactions across arbitrary token positions."
    s3 = "Transformer decoders generate output sequences autoregressively token by token."
    text = f"{s1} {s2} {s3}"

    chunks = chunk_text(text, chunk_size_tokens=22, chunk_overlap_tokens=0)
    assert len(chunks) >= 2
    # Ensure neither chunk cuts in the middle of a word or sentence
    for c in chunks:
        assert not c.startswith("etworks")
        assert not c.startswith("mechanisms")


def test_chunk_overlap():
    """Verify overlap preserves context across adjacent chunk boundaries."""
    s1 = "First statement introduces the overarching domain problem."
    s2 = "Second statement provides critical intermediary context."
    s3 = "Third statement presents empirical benchmark measurements."
    s4 = "Fourth statement outlines limitations and future investigations."
    text = f"{s1} {s2} {s3} {s4}"

    # Chunk with enough overlap to carry trailing sentence over
    chunks = chunk_text(text, chunk_size_tokens=35, chunk_overlap_tokens=15)
    assert len(chunks) >= 2

    # Verify that the second chunk contains content that was at the end of the first chunk
    # e.g., the boundary sentence appears in both Chunk 0 and Chunk 1
    found_overlap = False
    for i in range(len(chunks) - 1):
        words_chunk_a = set(chunks[i].split())
        words_chunk_b = set(chunks[i + 1].split())
        common = words_chunk_a.intersection(words_chunk_b)
        if len(common) >= 3:
            found_overlap = True
            break
    assert found_overlap, "Adjacent chunks should share overlapping words/sentences"


def test_chunk_no_overlap():
    """Verify that when chunk_overlap_tokens is 0, no sentences are duplicated."""
    s1 = "Alpha sentence is first."
    s2 = "Beta sentence is second."
    s3 = "Gamma sentence is third."
    text = f"{s1} {s2} {s3}"

    chunks = chunk_text(text, chunk_size_tokens=10, chunk_overlap_tokens=0)
    assert len(chunks) >= 2
    # With 0 overlap, "Alpha" should not appear in subsequent chunks
    assert "Alpha" not in " ".join(chunks[1:])


def test_chunk_text_edge_cases():
    """Verify behavior on empty text, short text, and massive unbroken tokens."""
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []

    # Text smaller than chunk size returns single chunk
    short_text = "Just a short note."
    result = chunk_text(short_text, chunk_size_tokens=800)
    assert result == [short_text]

    # Extreme continuous string without spaces
    huge_string = "X" * 200
    sliced = chunk_text(huge_string, chunk_size_tokens=10, chunk_overlap_tokens=2)
    assert len(sliced) >= 4
    assert all(len(s) <= 40 for s in sliced)


def test_note_chunking_metadata():
    """Verify notes produce chunks with source_id, sequential ordinals, stable IDs, and page_number=None."""
    source_id = "note-uuid-999"
    content = "First section of research notes.\n\nSecond section of research notes."

    chunks = create_chunks_for_note(source_id, content, chunk_size_tokens=500)
    assert len(chunks) >= 1
    for idx, c in enumerate(chunks):
        assert c.source_id == source_id
        assert c.ordinal == idx
        assert c.page_number is None
        assert c.id == generate_chunk_id(source_id, idx)
        assert c.token_estimate > 0
        assert c.text


def test_pdf_page_aware_chunking_preserves_page_numbers():
    """Verify PDF chunks strictly preserve 1-based page numbers across distinct pages."""
    source_id = "pdf-uuid-123"
    pages = [
        {"page_number": 1, "text": "Page one text discussing transformers."},
        {"page_number": 2, "text": "Page two text detailing self-attention."},
        {"page_number": 3, "text": "Page three text presenting ablation studies."},
    ]

    chunks = create_chunks_for_pdf_pages(source_id, pages, chunk_size_tokens=500)
    assert len(chunks) == 3

    assert chunks[0].page_number == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].id == generate_chunk_id(source_id, 0)
    assert "transformers" in chunks[0].text

    assert chunks[1].page_number == 2
    assert chunks[1].ordinal == 1
    assert chunks[1].id == generate_chunk_id(source_id, 1)
    assert "self-attention" in chunks[1].text

    assert chunks[2].page_number == 3
    assert chunks[2].ordinal == 2
    assert chunks[2].id == generate_chunk_id(source_id, 2)
    assert "ablation" in chunks[2].text


def test_pdf_page_aware_chunking_dense_page_multiple_chunks():
    """Verify a single long PDF page produces multiple chunks, all preserving the SAME page number."""
    source_id = "pdf-uuid-dense"
    dense_text = " ".join([f"Sentence {i} describing theorem {i}." for i in range(50)])
    pages = [{"page_number": 4, "text": dense_text}]

    chunks = create_chunks_for_pdf_pages(
        source_id, pages, chunk_size_tokens=25, chunk_overlap_tokens=5
    )
    assert len(chunks) > 1

    # Every chunk must preserve page 4
    for ordinal, c in enumerate(chunks):
        assert c.page_number == 4
        assert c.source_id == source_id
        assert c.ordinal == ordinal
        assert c.id == generate_chunk_id(source_id, ordinal)


def test_pdf_page_aware_chunking_skips_blank_pages():
    """Verify blank or whitespace-only PDF pages do not create empty chunks."""
    source_id = "pdf-uuid-blank"
    pages = [
        {"page_number": 1, "text": "Valid introductory content."},
        {"page_number": 2, "text": ""},  # Blank page
        {"page_number": 3, "text": "   \n  "},  # Whitespace-only page
        {"page_number": 4, "text": "Valid concluding remarks."},
    ]

    chunks = create_chunks_for_pdf_pages(source_id, pages)
    assert len(chunks) == 2

    assert chunks[0].page_number == 1
    assert chunks[0].ordinal == 0

    assert chunks[1].page_number == 4
    assert chunks[1].ordinal == 1  # Sequential ordinal 1


def test_api_note_creates_and_updates_chunks(client):
    """Verify creating a note persists chunks in SQLite and updating note replaces chunks transactionally."""
    # 1. Create a note with multi-paragraph content
    payload = {
        "title": "Quantum Computing Note",
        "content": "Qubits exhibit superposition.\n\nQuantum entanglement connects states.",
        "tags": ["Physics", "Quantum"],
    }
    create_res = client.post("/api/v1/notes", json=payload)
    assert create_res.status_code == 201
    note_id = create_res.json()["id"]

    # 2. Inspect chunks via GET /api/v1/sources/{id}/chunks
    chunk_res = client.get(f"/api/v1/sources/{note_id}/chunks")
    assert chunk_res.status_code == 200
    chunk_data = chunk_res.json()
    assert chunk_data["total"] >= 1
    first_chunk = chunk_data["items"][0]
    assert first_chunk["source_id"] == note_id
    assert first_chunk["page_number"] is None
    assert first_chunk["ordinal"] == 0
    assert first_chunk["id"] == generate_chunk_id(note_id, 0)

    # 3. Update note content and verify chunks are replaced
    update_res = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "Updated content: Topological qubits have superior coherence."},
    )
    assert update_res.status_code == 200

    updated_chunk_res = client.get(f"/api/v1/sources/{note_id}/chunks")
    assert updated_chunk_res.status_code == 200
    updated_data = updated_chunk_res.json()
    assert updated_data["total"] >= 1
    assert "Topological qubits" in updated_data["items"][0]["text"]
    assert "Qubits exhibit superposition" not in updated_data["items"][0]["text"]

    # 4. Delete note and verify cascade deletes all chunks
    del_res = client.delete(f"/api/v1/sources/{note_id}")
    assert del_res.status_code == 204

    get_chunk_res = client.get(f"/api/v1/sources/{note_id}/chunks")
    assert get_chunk_res.status_code == 404
