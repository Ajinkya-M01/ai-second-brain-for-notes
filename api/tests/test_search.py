"""Tests for embedding providers, vector store, indexing service, and search API.

All tests use FakeEmbeddingProvider and an in-memory ChromaDB client.
No live API calls are made. OPENROUTER_API_KEY is never read or required.
"""

import uuid
import pytest
import chromadb

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.embeddings import FakeEmbeddingProvider, NEMOTRON_EMBED_DIM
from app.ai import vector_store as vs
from app.api.routes.search import get_embedding_provider
from app.db.models import Base, Source, Chunk
from app.db.session import get_db
from app.main import app
from app.services.indexing import index_source, delete_source_vectors


# ---------------------------------------------------------------------------
# In-memory test database (separate from conftest to isolate this module)
# ---------------------------------------------------------------------------

SEARCH_TEST_DB_URL = "sqlite:///:memory:"

search_test_engine = create_engine(
    SEARCH_TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(search_test_engine, "connect")
def _set_pragma(dbapi_conn, rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SearchTestSession = sessionmaker(autocommit=False, autoflush=False, bind=search_test_engine)


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=search_test_engine)
    yield
    Base.metadata.drop_all(bind=search_test_engine)


@pytest.fixture
def db():
    conn = search_test_engine.connect()
    tx = conn.begin()
    session = SearchTestSession(bind=conn)
    yield session
    session.close()
    tx.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# In-memory ChromaDB fixture (reset between tests)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_chroma(monkeypatch):
    """Replace the ChromaDB collection singleton with a fresh in-memory collection per test."""
    client = chromadb.EphemeralClient()
    col_name = f"test_{uuid.uuid4().hex}"
    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )
    monkeypatch.setattr(vs, "_collection", collection)
    yield
    monkeypatch.setattr(vs, "_collection", None)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Search endpoint client with FakeEmbeddingProvider injected
# ---------------------------------------------------------------------------

@pytest.fixture
def search_client(db):
    fake_provider = FakeEmbeddingProvider()

    def override_db():
        yield db

    def override_provider():
        return fake_provider

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = override_provider

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


# ---------------------------------------------------------------------------
# Helper: create a Source with Chunks in the test DB
# ---------------------------------------------------------------------------

def _make_source(db, title: str, texts: list[str]) -> Source:
    source_id = str(uuid.uuid4())
    source = Source(
        id=source_id,
        kind="note",
        title=title,
        content=" ".join(texts),
        mime_type="text/plain",
        size_bytes=sum(len(t) for t in texts),
        content_sha256="abc" * 21 + "ab",
        status="pending",
    )
    db.add(source)
    db.flush()
    for ordinal, text in enumerate(texts):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            source_id=source_id,
            ordinal=ordinal,
            page_number=None,
            text=text,
            token_estimate=len(text) // 4 or 1,
        )
        db.add(chunk)
    db.commit()
    db.refresh(source)
    return source


# ===========================================================================
# Unit tests: FakeEmbeddingProvider
# ===========================================================================

def test_fake_provider_returns_correct_count():
    provider = FakeEmbeddingProvider()
    texts = ["hello world", "second sentence", "third text"]
    vecs = provider.embed(texts)
    assert len(vecs) == 3


def test_fake_provider_correct_dimension():
    provider = FakeEmbeddingProvider()
    vecs = provider.embed(["test"])
    assert len(vecs[0]) == NEMOTRON_EMBED_DIM


def test_fake_provider_deterministic():
    """Same text always produces the same vector."""
    provider = FakeEmbeddingProvider()
    text = "the attention mechanism"
    v1 = provider.embed([text])[0]
    v2 = provider.embed([text])[0]
    assert v1 == v2


def test_fake_provider_different_texts_differ():
    """Different texts produce different vectors."""
    provider = FakeEmbeddingProvider()
    v1 = provider.embed(["alpha text"])[0]
    v2 = provider.embed(["beta text"])[0]
    assert v1 != v2


def test_fake_provider_empty():
    provider = FakeEmbeddingProvider()
    assert provider.embed([]) == []


def test_fake_provider_normalized():
    """Vectors should be unit-length (L2 norm ≈ 1.0)."""
    import math
    provider = FakeEmbeddingProvider()
    vec = provider.embed(["normalize me"])[0]
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-4


# ===========================================================================
# Unit tests: vector_store upsert / query / delete
# ===========================================================================

def test_upsert_and_query_returns_hit():
    provider = FakeEmbeddingProvider()
    chunk_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    text = "neural networks learn via backpropagation"
    embedding = provider.embed([text])[0]

    vs.upsert_chunks([{
        "id": chunk_id,
        "embedding": embedding,
        "text": text,
        "source_id": source_id,
        "title": "ML Notes",
        "page_number": None,
    }])

    query_vec = provider.embed([text])[0]
    hits = vs.query_similar(query_vec, n_results=1)
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == chunk_id
    assert hits[0]["source_id"] == source_id
    assert hits[0]["title"] == "ML Notes"
    assert hits[0]["page_number"] is None
    assert hits[0]["similarity"] > 0.9  # same text → high similarity


def test_upsert_preserves_page_number():
    provider = FakeEmbeddingProvider()
    chunk_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    text = "page three content"
    embedding = provider.embed([text])[0]

    vs.upsert_chunks([{
        "id": chunk_id,
        "embedding": embedding,
        "text": text,
        "source_id": source_id,
        "title": "PDF Doc",
        "page_number": 3,
    }])

    hits = vs.query_similar(provider.embed([text])[0])
    assert hits[0]["page_number"] == 3


def test_delete_by_source_removes_vectors():
    provider = FakeEmbeddingProvider()
    source_id = str(uuid.uuid4())
    embedding = provider.embed(["content to delete"])[0]

    vs.upsert_chunks([{
        "id": str(uuid.uuid4()),
        "embedding": embedding,
        "text": "content to delete",
        "source_id": source_id,
        "title": "Temp",
        "page_number": None,
    }])

    vs.delete_by_source(source_id)
    hits = vs.query_similar(embedding)
    assert all(h["source_id"] != source_id for h in hits)


def test_query_empty_collection_returns_empty():
    provider = FakeEmbeddingProvider()
    qv = provider.embed(["anything"])[0]
    hits = vs.query_similar(qv)
    assert hits == []


# ===========================================================================
# Integration tests: indexing service
# ===========================================================================

def test_index_source_marks_indexed(db):
    source = _make_source(db, "Indexed Note", ["Attention is all you need."])
    provider = FakeEmbeddingProvider()

    index_source(db, source.id, provider)

    db.refresh(source)
    assert source.status == "indexed"


def test_index_source_upserts_vectors(db):
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Vector Note", ["Transformer encoders stack self-attention layers."])

    index_source(db, source.id, provider)

    qv = provider.embed(["self-attention layers"])[0]
    hits = vs.query_similar(qv, n_results=5)
    assert any(h["source_id"] == source.id for h in hits)


def test_index_source_reindex_replaces_vectors(db):
    """Re-indexing a source should not duplicate vectors."""
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Reindex Note", ["Original content here."])

    index_source(db, source.id, provider)
    index_source(db, source.id, provider)  # second call

    qv = provider.embed(["Original content here."])[0]
    hits = vs.query_similar(qv, n_results=20)
    source_hits = [h for h in hits if h["source_id"] == source.id]
    # Should be exactly 1 chunk (not 2 from two upserts)
    assert len(source_hits) == 1


def test_delete_source_vectors_removes_from_chroma(db):
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Delete Me", ["Text that will be removed."])
    index_source(db, source.id, provider)

    delete_source_vectors(source.id)

    qv = provider.embed(["Text that will be removed."])[0]
    hits = vs.query_similar(qv, n_results=5)
    assert all(h["source_id"] != source.id for h in hits)


# ===========================================================================
# API tests: POST /api/v1/search
# ===========================================================================

def test_search_returns_ranked_hits(search_client, db):
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Search Target", ["Self-attention allows each position to attend."])
    index_source(db, source.id, provider)

    response = search_client.post("/api/v1/search", json={"query": "self attention mechanism", "limit": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "self attention mechanism"
    assert data["total"] >= 1
    assert any(h["source_id"] == source.id for h in data["hits"])


def test_search_hit_has_all_fields(search_client, db):
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Field Test Note", ["Embedding vectors are stored in ChromaDB."])
    index_source(db, source.id, provider)

    response = search_client.post("/api/v1/search", json={"query": "embedding vectors", "limit": 1})
    assert response.status_code == 200
    hits = response.json()["hits"]
    assert len(hits) >= 1
    hit = hits[0]
    assert "chunk_id" in hit
    assert "source_id" in hit
    assert "title" in hit
    assert "excerpt" in hit
    assert "similarity" in hit
    assert isinstance(hit["similarity"], float)


def test_search_empty_collection_returns_empty(search_client):
    response = search_client.post("/api/v1/search", json={"query": "anything at all"})
    assert response.status_code == 200
    assert response.json()["hits"] == []
    assert response.json()["total"] == 0


def test_search_validates_empty_query(search_client):
    response = search_client.post("/api/v1/search", json={"query": ""})
    assert response.status_code == 422


def test_search_limit_respected(search_client, db):
    provider = FakeEmbeddingProvider()
    source = _make_source(db, "Multi Chunk", [
        "Chunk one about databases.",
        "Chunk two about vectors.",
        "Chunk three about retrieval.",
    ])
    index_source(db, source.id, provider)

    response = search_client.post("/api/v1/search", json={"query": "data", "limit": 2})
    assert response.status_code == 200
    assert len(response.json()["hits"]) <= 2


def test_search_no_api_key_returns_503(db):
    """Without OPENROUTER_API_KEY, search returns 503 with a clear message."""
    from app.core import config as cfg
    original_key = cfg.settings.OPENROUTER_API_KEY
    cfg.settings.OPENROUTER_API_KEY = None

    def override_db():
        conn = search_test_engine.connect()
        tx = conn.begin()
        session = SearchTestSession(bind=conn)
        try:
            yield session
        finally:
            session.close()
            tx.rollback()
            conn.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides.pop(get_embedding_provider, None)  # use real dependency

    try:
        with TestClient(app) as c:
            response = c.post("/api/v1/search", json={"query": "anything"})
        assert response.status_code == 503
        detail = response.json().get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("code") == "ai_not_configured"
    finally:
        cfg.settings.OPENROUTER_API_KEY = original_key
        app.dependency_overrides.pop(get_db, None)
