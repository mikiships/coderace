"""Tests for D3: publish integration (here.now API client)."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from coderace.cli import app
from coderace.publish import PublishError, PublishResult, publish_html
from coderace.store import ResultStore

runner = CliRunner()


def _mock_urlopen_success(step_responses: list[dict]):
    """Create a side_effect for urlopen that returns responses in order."""
    call_count = 0

    def side_effect(req, timeout=None):
        nonlocal call_count
        idx = call_count
        call_count += 1

        resp = MagicMock()
        if idx < len(step_responses):
            data = step_responses[idx]
            resp.read.return_value = json.dumps(data).encode("utf-8")
        else:
            resp.read.return_value = b"{}"
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        return resp

    return side_effect


class TestPublishHtml:
    def test_successful_anonymous_publish(self) -> None:
        responses = [
            {"id": "abc123", "upload_url": "https://upload.here.now/abc123"},
            {},  # PUT response (ignored)
            {"url": "https://here.now/abc123"},
        ]
        with patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)):
            result = publish_html("<html>test</html>")
        assert result.url == "https://here.now/abc123"
        assert result.publish_id == "abc123"
        assert result.expires is True

    def test_successful_authenticated_publish(self) -> None:
        responses = [
            {"id": "key123", "upload_url": "https://upload.here.now/key123"},
            {},
            {"url": "https://here.now/key123"},
        ]
        with patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)):
            result = publish_html("<html>test</html>", api_key="my-key")
        assert result.url == "https://here.now/key123"
        assert result.expires is False

    def test_api_key_from_env(self) -> None:
        responses = [
            {"id": "env123", "upload_url": "https://upload.here.now/env123"},
            {},
            {"url": "https://here.now/env123"},
        ]
        with patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)), \
             patch.dict("os.environ", {"HERENOW_API_KEY": "env-key"}):
            result = publish_html("<html>test</html>")
        assert result.expires is False

    def test_create_failure_raises(self) -> None:
        import urllib.error
        with patch("coderace.publish.urllib.request.urlopen", side_effect=urllib.error.URLError("connection failed")):
            with pytest.raises(PublishError, match="Failed to create upload"):
                publish_html("<html>test</html>")

    def test_upload_failure_raises(self) -> None:
        import urllib.error
        call_count = 0

        def side_effect(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                resp = MagicMock()
                resp.read.return_value = json.dumps({"id": "x", "upload_url": "https://up.here.now/x"}).encode()
                resp.__enter__ = lambda s: s
                resp.__exit__ = lambda s, *a: None
                return resp
            raise urllib.error.URLError("upload failed")

        with patch("coderace.publish.urllib.request.urlopen", side_effect=side_effect):
            with pytest.raises(PublishError, match="Failed to upload"):
                publish_html("<html>test</html>")

    def test_finalize_failure_raises(self) -> None:
        import urllib.error
        call_count = 0

        def side_effect(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                resp = MagicMock()
                if call_count == 1:
                    resp.read.return_value = json.dumps({"id": "x", "upload_url": "https://up.here.now/x"}).encode()
                else:
                    resp.read.return_value = b"{}"
                resp.__enter__ = lambda s: s
                resp.__exit__ = lambda s, *a: None
                return resp
            raise urllib.error.URLError("finalize failed")

        with patch("coderace.publish.urllib.request.urlopen", side_effect=side_effect):
            with pytest.raises(PublishError, match="Failed to finalize"):
                publish_html("<html>test</html>")

    def test_invalid_create_response_raises(self) -> None:
        responses = [{"unexpected": "data"}]
        with patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)):
            with pytest.raises(PublishError, match="Invalid response"):
                publish_html("<html>test</html>")

    def test_custom_api_base(self) -> None:
        responses = [
            {"id": "custom1", "upload_url": "https://custom.api/upload/custom1"},
            {},
            {"url": "https://custom.api/custom1"},
        ]
        calls = []
        inner = _mock_urlopen_success(responses)

        def tracking_urlopen(req, timeout=None):
            calls.append(req.full_url)
            return inner(req, timeout)

        with patch("coderace.publish.urllib.request.urlopen", side_effect=tracking_urlopen):
            result = publish_html("<html>test</html>", api_base="https://custom.api")
        assert calls[0] == "https://custom.api/publish"


def _populate_store(store: ResultStore) -> None:
    store.save_run("fizzbuzz", [
        {"agent": "claude", "composite_score": 85.0, "wall_time": 10.0,
         "lines_changed": 42, "tests_pass": True, "exit_clean": True,
         "lint_clean": True, "cost_usd": 0.05},
    ])


@pytest.fixture
def populated_store(tmp_path: Path) -> ResultStore:
    db_path = tmp_path / "test.db"
    store = ResultStore(db_path=db_path)
    _populate_store(store)
    yield store
    store.close()


class TestDashboardPublishCli:
    def test_publish_flag_shown_in_help(self) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert "--publish" in result.output
        assert "--here-now-key" in result.output

    def test_publish_success_prints_url(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "pub.html"
        responses = [
            {"id": "pub1", "upload_url": "https://upload.here.now/pub1"},
            {},
            {"url": "https://here.now/pub1"},
        ]
        with patch("coderace.store.get_db_path", return_value=db_path), \
             patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--publish"])
        assert result.exit_code == 0
        assert "https://here.now/pub1" in result.output
        assert "expires in 24h" in result.output

    def test_publish_with_key(self, populated_store: ResultStore, tmp_path: Path) -> None:
        db_path = populated_store._db_path
        output_path = tmp_path / "pub-key.html"
        responses = [
            {"id": "pk1", "upload_url": "https://upload.here.now/pk1"},
            {},
            {"url": "https://here.now/pk1"},
        ]
        with patch("coderace.store.get_db_path", return_value=db_path), \
             patch("coderace.publish.urllib.request.urlopen", side_effect=_mock_urlopen_success(responses)):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--publish", "--here-now-key", "mykey"])
        assert result.exit_code == 0
        assert "https://here.now/pk1" in result.output
        assert "expires" not in result.output

    def test_publish_failure_exits_1(self, populated_store: ResultStore, tmp_path: Path) -> None:
        import urllib.error
        db_path = populated_store._db_path
        output_path = tmp_path / "fail.html"
        with patch("coderace.store.get_db_path", return_value=db_path), \
             patch("coderace.publish.urllib.request.urlopen", side_effect=urllib.error.URLError("nope")):
            result = runner.invoke(app, ["dashboard", "-o", str(output_path), "--publish"])
        assert result.exit_code == 1
        assert "Publish failed" in result.output
