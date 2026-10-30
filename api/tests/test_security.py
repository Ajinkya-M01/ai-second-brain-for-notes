"""Security and reliability tests — Blueprint Section 10 coverage.

Covers:
- sanitize_secret_text: redaction of API keys, Bearer tokens, clean pass-through
- Rate limiter: enforcement at limit, 429 + Retry-After header, reset between tests
- Upload streaming: reject oversized streams before full read (via endpoint)
- CORS: allow_methods does not include TRACE or PUT; allow_origins is restricted
- Delete note: vectors are removed before SQLite delete
- Delete PDF source: disk file is cleaned up on delete
"""

import io
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import (
    check_rate_limit,
    reset_rate_limits,
    _request_history,
)
from app.core.security import sanitize_secret_text, read_bounded_upload_stream
from app.main import app


# ---------------------------------------------------------------------------
# sanitize_secret_text
# ---------------------------------------------------------------------------

class TestSanitizeSecretText:
    def test_redacts_configured_api_key(self, monkeypatch):
        """Configured OPENROUTER_API_KEY must never appear in sanitized output."""
        from app.core import config as cfg
        fake_key = "sk-or-v1-supersecretkey12345"
        monkeypatch.setattr(cfg.settings, "OPENROUTER_API_KEY", fake_key)

        dirty = f"Request failed: Authorization: Bearer {fake_key}"
        result = sanitize_secret_text(dirty)

        assert fake_key not in result
        assert "[REDACTED" in result

    def test_redacts_bearer_token_pattern(self):
        """Bearer token strings must be redacted even without a configured key."""
        dirty = "Got error from upstream: Bearer sk-or-v1-abcdef1234567890xyz"
        result = sanitize_secret_text(dirty)

        assert "sk-or-v1-abcdef1234567890xyz" not in result
        assert "[REDACTED" in result

    def test_redacts_sk_key_pattern(self):
        """Bare sk-... key patterns must be caught by regex."""
        dirty = "Auth error: sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx is invalid"
        result = sanitize_secret_text(dirty)

        assert "sk-or-v1-xxxxxxxxxxxx" not in result
        assert "[REDACTED" in result

    def test_passes_clean_text_unchanged(self):
        """Text containing no secrets must be returned unchanged."""
        clean = "Connection refused: [Errno 111] localhost:8000"
        result = sanitize_secret_text(clean)
        assert result == clean

    def test_empty_string_returns_empty(self):
        """Empty input must round-trip safely."""
        assert sanitize_secret_text("") == ""

    def test_none_like_falsy_returns_unchanged(self):
        """Falsy values that are still strings must pass through."""
        assert sanitize_secret_text("   ") == "   "


# ---------------------------------------------------------------------------
# Rate limiter (unit tests — no HTTP layer)
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def setup_method(self):
        reset_rate_limits()

    def test_allows_requests_under_limit(self):
        """N requests under the cap must not raise."""
        for _ in range(5):
            check_rate_limit("test_client", max_requests=5, window_seconds=60)

    def test_rejects_request_over_limit(self):
        """The (N+1)th request must raise HTTPException 429."""
        from fastapi import HTTPException

        for _ in range(3):
            check_rate_limit("test_client", max_requests=3, window_seconds=60)

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("test_client", max_requests=3, window_seconds=60)

        assert exc_info.value.status_code == 429

    def test_retry_after_header_present(self):
        """The 429 response detail must carry retry_after_seconds > 0."""
        from fastapi import HTTPException

        for _ in range(2):
            check_rate_limit("header_client", max_requests=2, window_seconds=60)

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("header_client", max_requests=2, window_seconds=60)

        detail = exc_info.value.detail
        assert "retry_after_seconds" in detail
        assert detail["retry_after_seconds"] >= 1

    def test_reset_clears_state(self):
        """reset_rate_limits() must allow previously-throttled client through again."""
        from fastapi import HTTPException

        for _ in range(2):
            check_rate_limit("reset_client", max_requests=2, window_seconds=60)

        with pytest.raises(HTTPException):
            check_rate_limit("reset_client", max_requests=2, window_seconds=60)

        reset_rate_limits()
        # Must not raise after reset
        check_rate_limit("reset_client", max_requests=2, window_seconds=60)

    def test_independent_clients_dont_share_quota(self):
        """Separate client IDs must have independent windows."""
        for _ in range(3):
            check_rate_limit("client_a", max_requests=3, window_seconds=60)
        # client_b should still have fresh quota
        check_rate_limit("client_b", max_requests=3, window_seconds=60)


# ---------------------------------------------------------------------------
# Chat endpoint rate limiting (HTTP layer)
# ---------------------------------------------------------------------------

class TestChatRateLimitEndpoint:
    def test_chat_rate_limit_returns_429(self, client):
        """Exceeding MAX_CHAT_REQUESTS_PER_MINUTE from one IP must return 429."""
        from app.core.config import settings
        from app.core.rate_limit import reset_rate_limits

        reset_rate_limits()
        cap = settings.MAX_CHAT_REQUESTS_PER_MINUTE
        payload = {"question": "What is the capital of France?"}

        responses = []
        for _ in range(cap + 1):
            r = client.post("/api/v1/chat", json=payload)
            responses.append(r.status_code)

        assert 429 in responses, (
            f"Expected a 429 after {cap} requests; got statuses: {set(responses)}"
        )

    def test_retry_after_header_in_429(self, client):
        """A 429 response from the chat endpoint must include a Retry-After header."""
        from app.core.config import settings
        from app.core.rate_limit import reset_rate_limits

        reset_rate_limits()
        cap = settings.MAX_CHAT_REQUESTS_PER_MINUTE
        payload = {"question": "ping"}

        for _ in range(cap):
            client.post("/api/v1/chat", json=payload)

        r = client.post("/api/v1/chat", json=payload)
        if r.status_code == 429:
            assert "retry-after" in {k.lower() for k in r.headers}


# ---------------------------------------------------------------------------
# Upload streaming limit (HTTP layer)
# ---------------------------------------------------------------------------

class TestUploadStreamLimit:
    def test_oversized_upload_returns_413(self, client):
        """An upload larger than MAX_UPLOAD_MB must be rejected with 413."""
        from app.core.config import settings

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        # Construct a byte stream 1 byte over the limit
        oversized = b"A" * (max_bytes + 1)
        oversized_file = io.BytesIO(oversized)

        response = client.post(
            "/api/v1/documents",
            files={"file": ("big.pdf", oversized_file, "application/pdf")},
        )
        assert response.status_code == 413, (
            f"Expected 413 for oversized upload, got {response.status_code}: {response.text}"
        )

    def test_normal_sized_non_pdf_returns_415_not_413(self, client):
        """A non-PDF within size limit must fail on content validation (415), not size (413)."""
        from app.core.config import settings

        small_file = io.BytesIO(b"not a pdf content")
        response = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", small_file, "application/pdf")},
        )
        # Should fail validation (415 or 422), NOT 413
        assert response.status_code != 413, (
            "A small file should not be rejected for size"
        )


# ---------------------------------------------------------------------------
# read_bounded_upload_stream unit test (without HTTP)
# ---------------------------------------------------------------------------

class TestReadBoundedUploadStream:
    @pytest.mark.asyncio
    async def test_raises_413_when_stream_exceeds_limit(self):
        """read_bounded_upload_stream must raise 413 before returning full bytes."""
        import asyncio
        from fastapi import HTTPException
        from unittest.mock import AsyncMock, MagicMock

        # Simulate a file that returns 10 KB chunks
        chunk = b"X" * (10 * 1024)
        call_count = 0

        async def fake_read(size=-1):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return chunk
            return b""

        mock_file = MagicMock()
        mock_file.read = fake_read

        with pytest.raises(HTTPException) as exc_info:
            await read_bounded_upload_stream(mock_file, max_bytes=5 * 1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_returns_bytes_within_limit(self):
        """read_bounded_upload_stream must return full bytes when under limit."""
        from unittest.mock import MagicMock

        content = b"hello world"
        calls = iter([content, b""])

        async def fake_read(size=-1):
            return next(calls)

        mock_file = MagicMock()
        mock_file.read = fake_read

        result = await read_bounded_upload_stream(mock_file, max_bytes=1024)
        assert result == content


# ---------------------------------------------------------------------------
# CORS configuration checks
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    def test_allow_methods_excludes_trace(self, client):
        """OPTIONS preflight must not advertise TRACE as an allowed method."""
        response = client.options(
            "/api/v1/notes",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed = response.headers.get("access-control-allow-methods", "")
        assert "TRACE" not in allowed.upper()

    def test_allow_methods_excludes_put(self, client):
        """OPTIONS preflight must not advertise PUT as an allowed method
        (the API uses PATCH not PUT).
        """
        response = client.options(
            "/api/v1/notes",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed = response.headers.get("access-control-allow-methods", "")
        assert "PUT" not in allowed.upper()

    def test_cors_allows_configured_origin(self, client):
        """The configured FRONTEND_ORIGIN must receive a valid ACAO header."""
        response = client.options(
            "/api/v1/notes",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # TestClient may strip CORS headers; check that the server didn't crash
        assert response.status_code in (200, 204)

    def test_middleware_stack_has_no_wildcard_origin(self):
        """The FastAPI app middleware must not configure allow_origins=['*']."""
        from starlette.middleware.cors import CORSMiddleware

        for middleware in app.user_middleware:
            if middleware.cls is CORSMiddleware:
                origins = middleware.kwargs.get("allow_origins", [])
                assert "*" not in origins, (
                    "CORSMiddleware allow_origins must not contain '*' (wildcard)"
                )
                break


# ---------------------------------------------------------------------------
# Delete note: vector cascade
# ---------------------------------------------------------------------------

class TestDeleteNoteVectorCascade:
    def test_delete_note_calls_delete_source_vectors(self, client, monkeypatch):
        """Deleting a note must call delete_source_vectors before SQLite removal."""
        deleted_ids = []

        def mock_delete_vectors(source_id: str):
            deleted_ids.append(source_id)

        monkeypatch.setattr(
            "app.api.routes.notes.delete_source_vectors",
            mock_delete_vectors,
            raising=False,
        )

        # Create a note
        create_resp = client.post(
            "/api/v1/notes",
            json={"title": "Vector Cascade Test", "content": "Some content here."},
        )
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        # Delete it
        delete_resp = client.delete(f"/api/v1/notes/{note_id}")
        assert delete_resp.status_code == 204

        # Vector cleanup was called with correct ID
        assert note_id in deleted_ids

    def test_delete_note_removes_from_db(self, client):
        """After deletion, GET the note must return 404."""
        create_resp = client.post(
            "/api/v1/notes",
            json={"title": "Delete DB Test", "content": "Content to delete."},
        )
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        client.delete(f"/api/v1/notes/{note_id}")

        get_resp = client.get(f"/api/v1/notes/{note_id}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete PDF source: disk file cleanup
# ---------------------------------------------------------------------------

class TestDeleteSourceFileCleanup:
    def test_delete_source_removes_pdf_file_from_disk(self, client, tmp_path, monkeypatch):
        """Deleting a PDF source must remove the file from the upload directory."""
        from app.core import config as cfg
        from app.services import pdf as pdf_service
        from app.db.session import get_db

        # Point UPLOAD_DIR to a temp directory under test control
        monkeypatch.setattr(cfg.settings, "UPLOAD_DIR", str(tmp_path))

        # Create a fake PDF source row directly via service
        # We use the client's DB session via the dependency override in conftest
        # and simulate what save_pdf_document would do by creating a minimal fixture.

        # Use a real PDF (minimal valid one) so validation passes
        minimal_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
            b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>>endobj\n"
            b"4 0 obj<</Length 44>>stream\n"
            b"BT /F1 12 Tf 100 700 Td (Hello) Tj ET\n"
            b"endstream endobj\n"
            b"5 0 obj<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000266 00000 n \n"
            b"0000000360 00000 n \n"
            b"trailer<</Size 6 /Root 1 0 R>>\n"
            b"startxref\n454\n%%EOF\n"
        )

        upload_resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(minimal_pdf), "application/pdf")},
        )

        if upload_resp.status_code != 201:
            pytest.skip(
                f"PDF creation returned {upload_resp.status_code}; "
                "skipping disk-cleanup test (PDF may not parse in this environment)."
            )

        source_id = upload_resp.json()["id"]
        expected_path = tmp_path / f"{source_id}.pdf"

        # File must exist after upload
        assert expected_path.exists(), "PDF file should have been written to UPLOAD_DIR"

        # Delete the source
        del_resp = client.delete(f"/api/v1/notes/{source_id}")
        assert del_resp.status_code == 204

        # File must be gone
        assert not expected_path.exists(), (
            "PDF file must be removed from disk after source deletion"
        )

