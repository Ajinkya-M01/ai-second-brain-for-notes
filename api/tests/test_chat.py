"""Tests for Grounded Q&A chat completions, citation validation, and no-evidence fallback.

All tests use FakeEmbeddingProvider and FakeGenerationProvider with in-memory ChromaDB.
No live API calls are made. OPENROUTER_API_KEY is never read or required for tests.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.ai.embeddings import FakeEmbeddingProvider
from app.ai.generation import FakeGenerationProvider
from app.ai import vector_store as vs
from app.api.routes.chat import get_generation_provider
from app.api.routes.search import get_embedding_provider
from app.core import config as cfg
from app.db.session import get_db
from app.main import app
from app.services.chat import (
    NO_EVIDENCE_ANSWER,
    SYSTEM_PROMPT,
    answer_question,
    build_evidence_prompt,
    validate_and_extract_citations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_test_chunks(texts_with_meta: list[dict]) -> list[dict]:
    """Helper to embed and upsert chunks into ChromaDB for search testing."""
    provider = FakeEmbeddingProvider()
    chunks = []
    for item in texts_with_meta:
        chunk_id = item.get("id", str(uuid.uuid4()))
        text = item["text"]
        embedding = provider.embed([text])[0]
        chunk = {
            "id": chunk_id,
            "embedding": embedding,
            "text": text,
            "source_id": item.get("source_id", str(uuid.uuid4())),
            "title": item.get("title", "Test Title"),
            "page_number": item.get("page_number", None),
        }
        chunks.append(chunk)

    vs.upsert_chunks(chunks)
    return chunks


# ===========================================================================
# Unit Tests: Prompt Assembly & Citation Validation
# ===========================================================================

def test_build_evidence_prompt_formatting():
    """Verify evidence chunks are formatted with stable [S1], [S2] labels and untrusted delimiters."""
    chunks = [
        {
            "chunk_id": "c1",
            "source_id": "s1",
            "title": "Machine Learning Notes",
            "page_number": None,
            "text": "Transformers rely on attention mechanisms.",
        },
        {
            "chunk_id": "c2",
            "source_id": "s2",
            "title": "Attention Paper.pdf",
            "page_number": 3,
            "text": "Multi-head attention allows joint information attendance.",
        },
    ]

    prompt_text, label_map = build_evidence_prompt(chunks)

    assert "[S1] Source: \"Machine Learning Notes\"" in prompt_text
    assert "[S2] Source: \"Attention Paper.pdf\" (Page 3)" in prompt_text
    assert "Transformers rely on attention mechanisms." in prompt_text
    assert "Multi-head attention allows joint information attendance." in prompt_text
    assert "[S1]" in label_map
    assert "[S2]" in label_map
    assert label_map["[S1]"]["chunk_id"] == "c1"
    assert label_map["[S2]"]["page_number"] == 3


def test_validate_and_extract_citations_valid():
    """Valid citations should resolve to backend metadata."""
    label_map = {
        "[S1]": {
            "chunk_id": "c1",
            "source_id": "s1",
            "title": "Python Architecture",
            "page_number": None,
            "text": "FastAPI is a modern web framework.",
        },
        "[S2]": {
            "chunk_id": "c2",
            "source_id": "s2",
            "title": "Architecture.pdf",
            "page_number": 5,
            "text": "SQLAlchemy handles ORM mapping.",
        },
    }

    answer = "FastAPI is fast [S1], and SQLAlchemy manages database models [S2]."
    citations = validate_and_extract_citations(answer, label_map)

    assert len(citations) == 2
    assert citations[0].label == "[S1]"
    assert citations[0].chunk_id == "c1"
    assert citations[0].title == "Python Architecture"
    assert citations[0].page_number is None

    assert citations[1].label == "[S2]"
    assert citations[1].chunk_id == "c2"
    assert citations[1].title == "Architecture.pdf"
    assert citations[1].page_number == 5


def test_validate_and_extract_citations_drops_invented():
    """Model-invented citations ([S99], [S42], [Doc1]) must be dropped completely."""
    label_map = {
        "[S1]": {
            "chunk_id": "c1",
            "source_id": "s1",
            "title": "Real Document",
            "page_number": 1,
            "text": "Real verified facts.",
        }
    }

    # Answer contains valid [S1] plus invented [S99], [S42], and arbitrary references
    answer = (
        "Here is the verified claim [S1]. "
        "Here is a hallucinated claim [S99] and another one [S42] referencing [Doc9]."
    )
    citations = validate_and_extract_citations(answer, label_map)

    assert len(citations) == 1
    assert citations[0].label == "[S1]"
    assert citations[0].chunk_id == "c1"


def test_validate_and_extract_citations_deduplicates():
    """Repeated references to the same citation [S1] should appear once in metadata."""
    label_map = {
        "[S1]": {
            "chunk_id": "c1",
            "source_id": "s1",
            "title": "Doc",
            "page_number": None,
            "text": "Some text",
        }
    }
    answer = "First mention [S1]. Second mention of same point [S1]."
    citations = validate_and_extract_citations(answer, label_map)

    assert len(citations) == 1
    assert citations[0].label == "[S1]"


# ===========================================================================
# Service Tests: answer_question()
# ===========================================================================

def test_answer_question_no_evidence_skips_generation():
    """When vector store returns no matches, return clear message without calling LLM."""
    embed_provider = FakeEmbeddingProvider()
    fake_generator = FakeGenerationProvider()

    # Chroma is empty
    response = answer_question(
        question="What is the speed of light?",
        embedding_provider=embed_provider,
        generation_provider=fake_generator,
        min_similarity=0.8,
    )

    assert response.grounded is False
    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.citations == []
    assert response.retrieved_chunks_count == 0
    # Crucial: verify LLM was NEVER called
    assert fake_generator.call_count == 0


def test_answer_question_with_valid_evidence_and_citations():
    """When evidence exists, LLM is called and citations are extracted."""
    embed_provider = FakeEmbeddingProvider()
    text = "Photosynthesis converts carbon dioxide and water into glucose and oxygen."
    _upsert_test_chunks([
        {
            "id": "chunk-bio-1",
            "source_id": "source-bio-1",
            "title": "Biology Notes",
            "page_number": 12,
            "text": text,
        }
    ])

    fake_generator = FakeGenerationProvider(
        default_response="Photosynthesis produces glucose and oxygen from carbon dioxide [S1]."
    )

    response = answer_question(
        question="What does photosynthesis produce?",
        embedding_provider=embed_provider,
        generation_provider=fake_generator,
        min_similarity=0.0,
    )

    assert response.grounded is True
    assert fake_generator.call_count == 1
    assert len(response.citations) == 1
    assert response.citations[0].label == "[S1]"
    assert response.citations[0].title == "Biology Notes"
    assert response.citations[0].page_number == 12
    assert response.citations[0].chunk_id == "chunk-bio-1"

    # Verify untrusted framing in prompt
    last_messages = fake_generator.last_messages
    assert last_messages[0]["role"] == "system"
    assert "CRITICAL GROUNDING & SECURITY RULES" in last_messages[0]["content"]
    assert "--- EVIDENCE START ---" in last_messages[1]["content"]
    assert "Question: What does photosynthesis produce?" in last_messages[1]["content"]


def test_answer_question_all_invented_citations_marks_ungrounded():
    """If the model generates an answer with only invented citations, grounded is False."""
    embed_provider = FakeEmbeddingProvider()
    _upsert_test_chunks([
        {
            "id": "c-1",
            "source_id": "s-1",
            "title": "Source 1",
            "text": "Some verified context.",
        }
    ])

    fake_generator = FakeGenerationProvider(
        default_response="This answer only cites hallucinated sources [S99] and [S500]."
    )

    response = answer_question(
        question="Test question",
        embedding_provider=embed_provider,
        generation_provider=fake_generator,
        min_similarity=0.0,
    )

    # All citations were invented, so citations list is empty and grounded is False
    assert response.citations == []
    assert response.grounded is False


# ===========================================================================
# API Route Tests: POST /api/v1/chat
# ===========================================================================

@pytest.fixture
def chat_client(db_session):
    """Client with FakeEmbeddingProvider and FakeGenerationProvider overrides."""
    fake_embed = FakeEmbeddingProvider()
    fake_gen = FakeGenerationProvider(
        default_response="Transformers process input in parallel [S1]."
    )

    def override_embed():
        return fake_embed

    def override_gen():
        return fake_gen

    app.dependency_overrides[get_embedding_provider] = override_embed
    app.dependency_overrides[get_generation_provider] = override_gen

    with TestClient(app) as test_client:
        test_client.fake_gen = fake_gen  # attach for assertions
        test_client.fake_embed = fake_embed
        yield test_client

    app.dependency_overrides.pop(get_embedding_provider, None)
    app.dependency_overrides.pop(get_generation_provider, None)


def test_chat_api_success_with_citations(chat_client):
    """POST /api/v1/chat returns 200 with grounded answer and citations."""
    _upsert_test_chunks([
        {
            "id": "chunk-ai-1",
            "source_id": "source-ai-1",
            "title": "Attention Is All You Need",
            "page_number": 2,
            "text": "The Transformer is the first transduction model relying entirely on self-attention.",
        }
    ])

    response = chat_client.post(
        "/api/v1/chat",
        json={"question": "What is the Transformer architecture?", "limit": 3, "min_similarity": 0.0},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "What is the Transformer architecture?"
    assert data["grounded"] is True
    assert len(data["citations"]) == 1
    assert data["citations"][0]["label"] == "[S1]"
    assert data["citations"][0]["title"] == "Attention Is All You Need"
    assert data["citations"][0]["page_number"] == 2
    assert data["citations"][0]["chunk_id"] == "chunk-ai-1"


def test_chat_api_no_evidence_returns_clear_message(chat_client):
    """POST /api/v1/chat with no matching documents returns standard no-evidence message."""
    response = chat_client.post(
        "/api/v1/chat",
        json={"question": "What is quantum gravity?", "min_similarity": 0.95},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["grounded"] is False
    assert data["answer"] == NO_EVIDENCE_ANSWER
    assert data["citations"] == []
    assert data["retrieved_chunks_count"] == 0
    assert chat_client.fake_gen.call_count == 0


def test_chat_api_invented_citation_dropped(chat_client):
    """POST /api/v1/chat drops hallucinated citations and keeps valid ones."""
    _upsert_test_chunks([
        {
            "id": "chunk-python-1",
            "source_id": "source-python-1",
            "title": "Python Guide",
            "page_number": 1,
            "text": "Python uses dynamic typing.",
        }
    ])

    chat_client.fake_gen.default_response = (
        "Python is dynamically typed [S1], but invented citations [S99] are ignored."
    )

    response = chat_client.post(
        "/api/v1/chat",
        json={"question": "Tell me about Python typing", "min_similarity": 0.0},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["grounded"] is True
    # Only [S1] should be in citations, [S99] must be dropped
    labels = [c["label"] for c in data["citations"]]
    assert labels == ["[S1]"]


def test_chat_api_validation_error_on_empty_question(chat_client):
    """Empty question returns 422 Unprocessable Entity."""
    response = chat_client.post("/api/v1/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_api_validation_error_on_oversized_question(chat_client):
    """Question exceeding 1000 characters returns 422 Unprocessable Entity."""
    long_q = "a" * 1001
    response = chat_client.post("/api/v1/chat", json={"question": long_q})
    assert response.status_code == 422


def test_chat_api_returns_503_when_no_api_key(client):
    """When OPENROUTER_API_KEY is not set, chat endpoint returns 503."""
    original_key = cfg.settings.OPENROUTER_API_KEY
    cfg.settings.OPENROUTER_API_KEY = None

    try:
        response = client.post("/api/v1/chat", json={"question": "Hello?"})
        assert response.status_code == 503
        data = response.json()
        assert data.get("detail", {}).get("code") == "ai_not_configured"
    finally:
        cfg.settings.OPENROUTER_API_KEY = original_key

