"""Tests for Notes CRUD API endpoints and data model."""

import hashlib


def test_readiness_check(client):
    """Verify GET /api/v1/health/ready verifies DB connectivity."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_create_note_success(client):
    """Verify creating a valid note computes hash, size, and normalizes tags."""
    content = "# FastAPI Architecture\nClean modular layout with SQLAlchemy."
    payload = {
        "title": "FastAPI Architecture",
        "content": content,
        "tags": ["Backend", "Python", "  AI-Research  "],
    }
    response = client.post("/api/v1/notes", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["kind"] == "note"
    assert data["title"] == "FastAPI Architecture"
    assert data["content"] == content
    assert data["mime_type"] == "text/plain"
    assert data["size_bytes"] == len(content.encode("utf-8"))
    assert data["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert data["status"] in ("pending", "indexed")
    assert set(data["tags"]) == {"backend", "python", "ai-research"}


def test_create_note_validation_failure(client):
    """Verify validation rejects missing or empty title."""
    # Empty title
    response = client.post(
        "/api/v1/notes",
        json={"title": "", "content": "Some content here"},
    )
    assert response.status_code == 422

    # Missing title
    response = client.post(
        "/api/v1/notes",
        json={"content": "Some content without title"},
    )
    assert response.status_code == 422


def test_get_note_by_id(client):
    """Verify retrieving a single note by ID."""
    create_res = client.post(
        "/api/v1/notes",
        json={"title": "Note 1", "content": "Content 1", "tags": ["tag1"]},
    )
    note_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/notes/{note_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == note_id
    assert get_res.json()["title"] == "Note 1"


def test_get_note_not_found(client):
    """Verify 404 for unknown note ID."""
    response = client.get("/api/v1/notes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


def test_list_notes_with_pagination(client):
    """Verify listing notes with limit and offset."""
    for i in range(5):
        client.post(
            "/api/v1/notes",
            json={"title": f"Note {i}", "content": f"Content {i}"},
        )

    # Fetch first page of 2
    res_p1 = client.get("/api/v1/notes?limit=2&offset=0")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1["items"]) == 2
    assert data_p1["total"] == 5
    assert data_p1["limit"] == 2
    assert data_p1["offset"] == 0

    # Fetch second page of 2
    res_p2 = client.get("/api/v1/notes?limit=2&offset=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["items"]) == 2


def test_list_notes_filter_by_tag(client):
    """Verify filtering notes by tag."""
    client.post(
        "/api/v1/notes",
        json={"title": "Docker Setup", "content": "Compose instructions", "tags": ["devops"]},
    )
    client.post(
        "/api/v1/notes",
        json={"title": "ML Transformers", "content": "Attention paper notes", "tags": ["ml"]},
    )

    response = client.get("/api/v1/notes?tag=devops")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Docker Setup"


def test_list_notes_search_query(client):
    """Verify search filter across title and content."""
    client.post(
        "/api/v1/notes",
        json={"title": "Vector Databases", "content": "Chroma and embeddings"},
    )
    client.post(
        "/api/v1/notes",
        json={"title": "Cooking Recipe", "content": "Pasta ingredients"},
    )

    # Search for vector
    response = client.get("/api/v1/notes?q=vector")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Vector Databases"

    # Search in content for chroma
    response_content = client.get("/api/v1/notes?q=chroma")
    assert response_content.status_code == 200
    assert response_content.json()["total"] == 1


def test_update_note(client):
    """Verify updating title, content, and tags."""
    create_res = client.post(
        "/api/v1/notes",
        json={"title": "Original Title", "content": "Original Content", "tags": ["tagA"]},
    )
    note_id = create_res.json()["id"]

    new_content = "Updated Content with different length"
    update_res = client.patch(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "New Title",
            "content": new_content,
            "tags": ["tagA", "tagB"],
        },
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["title"] == "New Title"
    assert data["content"] == new_content
    assert data["size_bytes"] == len(new_content.encode("utf-8"))
    assert data["content_sha256"] == hashlib.sha256(new_content.encode("utf-8")).hexdigest()
    assert set(data["tags"]) == {"taga", "tagb"}


def test_update_note_not_found(client):
    """Verify 404 when updating non-existent note."""
    response = client.patch(
        "/api/v1/notes/00000000-0000-0000-0000-000000000000",
        json={"title": "Does not exist"},
    )
    assert response.status_code == 404


def test_delete_note(client):
    """Verify deleting a note removes it from database."""
    create_res = client.post(
        "/api/v1/notes",
        json={"title": "To Delete", "content": "Temporary content", "tags": ["temp"]},
    )
    note_id = create_res.json()["id"]

    # Delete
    del_res = client.delete(f"/api/v1/notes/{note_id}")
    assert del_res.status_code == 204

    # Confirm it's gone
    get_res = client.get(f"/api/v1/notes/{note_id}")
    assert get_res.status_code == 404


def test_delete_note_not_found(client):
    """Verify 404 when deleting non-existent note."""
    response = client.delete("/api/v1/notes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_generic_sources_api(client):
    """Verify Blueprint Section 6 generic /api/v1/sources endpoints work with note sources."""
    create_res = client.post(
        "/api/v1/notes",
        json={"title": "Source Note", "content": "Content of source note", "tags": ["source-tag"]},
    )
    source_id = create_res.json()["id"]

    # List sources
    list_res = client.get("/api/v1/sources?kind=note")
    assert list_res.status_code == 200
    assert any(s["id"] == source_id for s in list_res.json()["items"])

    # Get single source
    get_res = client.get(f"/api/v1/sources/{source_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Source Note"
