import uuid
import chromadb
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.embeddings import FakeEmbeddingProvider
from app.ai.generation import FakeGenerationProvider
from app.ai import vector_store as vs
from app.core.rate_limit import reset_rate_limits
from app.db.models import Base
from app.db.session import get_db
from app.main import app

# In-memory SQLite with StaticPool so all threads/sessions share the same in-memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables in memory once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a transactional database session per test function."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Provide a FastAPI TestClient configured to use the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_embedding_and_chroma(monkeypatch):
    """Ensure no test ever calls live OpenRouter and each test has an isolated Chroma collection."""
    client = chromadb.EphemeralClient()
    col_name = f"test_{uuid.uuid4().hex}"
    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )
    monkeypatch.setattr(vs, "_collection", collection)
    monkeypatch.setattr(
        "app.ai.embeddings.OpenRouterEmbeddingProvider",
        FakeEmbeddingProvider,
    )
    monkeypatch.setattr(
        "app.ai.generation.OpenRouterGenerationProvider",
        FakeGenerationProvider,
    )
    # Reset per-test so rate-limit state never bleeds between tests
    reset_rate_limits()
    yield
    monkeypatch.setattr(vs, "_collection", None)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
