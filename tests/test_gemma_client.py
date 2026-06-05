"""
tests/test_gemma_client.py — Tests for GemmaClient

Tests:
    - Unit tests: mock Ollama, test logic without server
    - Integration tests: require running Ollama (SKIP_OLLAMA_TESTS=false)

Run:
    pytest tests/test_gemma_client.py -v
    pytest tests/test_gemma_client.py -v -k "not integration"  # skip integration tests
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.core.gemma_client import (
    GemmaClient,
    GemmaConnectionError,
    GemmaResponseError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fake_ollama_sdk_for_unit_tests(monkeypatch):
    """Unit tests should not require the Ollama SDK to be installed.

    When integration tests are explicitly enabled with SKIP_OLLAMA_TESTS=false,
    this fixture leaves imports untouched so the real SDK/server path is tested.
    """
    if os.getenv("SKIP_OLLAMA_TESTS", "true").lower() != "true":
        return

    fake_ollama = MagicMock()
    fake_ollama.Client = MagicMock(return_value=MagicMock())
    fake_ollama.ResponseError = Exception
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

@pytest.fixture
def client_config() -> Dict[str, Any]:
    """Default GemmaClient configuration for tests."""
    return {
        "model": "gemma4:e4b",
        "host": "http://localhost:11434",
        "timeout": 30,
    }


@pytest.fixture
def mock_client(client_config: Dict[str, Any]) -> GemmaClient:
    """GemmaClient with mocked _client (ollama.Client)."""
    client = GemmaClient(**client_config)
    client._client = MagicMock()
    client._ollama = MagicMock()
    client._ollama.ResponseError = Exception
    return client


@pytest.fixture
def red_png_image(tmp_path: Path) -> Path:
    """Create a small 100x100 red PNG image using Pillow."""
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img_path = tmp_path / "red.png"
        img.save(str(img_path))
        return img_path
    except ImportError:
        pytest.skip("Pillow not installed, skipping image tests")


@pytest.fixture
def live_client() -> GemmaClient:
    """Real GemmaClient for integration tests."""
    return GemmaClient()


# ---------------------------------------------------------------------------
# Unit tests (no Ollama needed)
# ---------------------------------------------------------------------------

class TestGemmaClientUnit:
    """Unit tests using mocks, no Ollama server required."""

    def test_default_init(self):
        """GemmaClient initializes with defaults from class constants."""
        client = GemmaClient()
        assert client.model == "gemma4:e4b"
        assert client.host == "http://localhost:11434"
        assert client.timeout == 120

    def test_custom_init(self, client_config: Dict[str, Any]):
        """GemmaClient stores custom model, host, and timeout."""
        client = GemmaClient(**client_config)
        assert client.model == client_config["model"]
        assert client.host == client_config["host"]
        assert client.timeout == client_config["timeout"]

    def test_model_from_env(self, monkeypatch):
        """OLLAMA_MODEL env var overrides default model."""
        monkeypatch.setenv("OLLAMA_MODEL", "custom:model")
        client = GemmaClient()
        assert client.model == "custom:model"

    def test_invalid_timeout_raises(self):
        """Timeout <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            GemmaClient(timeout=0)

    def test_empty_prompt_raises_generate(self, mock_client: GemmaClient):
        """generate() raises ValueError for empty prompt."""
        with pytest.raises(ValueError, match="prompt must not be empty"):
            mock_client.generate("")

    def test_empty_prompt_raises_think(self, mock_client: GemmaClient):
        """think() raises ValueError for empty prompt."""
        with pytest.raises(ValueError, match="prompt must not be empty"):
            mock_client.think("")

    def test_missing_image_raises(self, mock_client: GemmaClient, tmp_path: Path):
        """analyze_image() raises FileNotFoundError for missing file."""
        nonexistent = tmp_path / "missing.png"
        with pytest.raises(FileNotFoundError, match="Image not found"):
            mock_client.analyze_image(nonexistent, "test")

    def test_image_too_large_raises(self, mock_client: GemmaClient, tmp_path: Path):
        """analyze_image() raises ValueError for file > 10 MB."""
        large_file = tmp_path / "large.png"
        large_file.write_bytes(b"x" * (11 * 1024 * 1024))  # 11 MB
        with pytest.raises(ValueError, match="Image file too large"):
            mock_client.analyze_image(large_file, "test")

    def test_empty_prompt_raises_analyze_image(self, mock_client: GemmaClient, red_png_image: Path):
        """analyze_image() raises ValueError for empty prompt."""
        with pytest.raises(ValueError, match="prompt must not be empty"):
            mock_client.analyze_image(red_png_image, "")

    def test_chat_with_retry_includes_num_ctx(self, mock_client: GemmaClient):
        """Verify DEFAULT_NUM_CTX and temperature are passed to Ollama SDK."""
        mock_client._client.chat.return_value = {"message": {"content": "ok"}}
        with patch("time.sleep"):
            mock_client.generate("test prompt")
        _, kwargs = mock_client._client.chat.call_args
        assert "options" in kwargs
        assert kwargs["options"]["num_ctx"] == GemmaClient.DEFAULT_NUM_CTX
        assert kwargs["options"]["temperature"] == 0.3

    def test_retry_exhausted_raises_connection_error(self, mock_client: GemmaClient):
        """3x retries raise GemmaConnectionError quickly."""
        try:
            import httpx
            mock_client._httpx = httpx
            mock_client._client.chat.side_effect = httpx.ConnectError("connection refused")
            with patch("time.sleep"):
                with pytest.raises(GemmaConnectionError):
                    mock_client.generate("test")
        except ImportError:
            pytest.skip("httpx not installed")

    def test_is_available_false_when_model_missing(self, mock_client: GemmaClient):
        """is_available() returns False if model not in list."""
        mock_client._client.list.return_value = {"models": [{"model": "other:model"}]}
        assert mock_client.is_available() is False

    def test_is_available_false_on_exception(self, mock_client: GemmaClient):
        """is_available() returns False on ResponseError."""
        mock_client._client.list.side_effect = Exception("ResponseError")
        assert mock_client.is_available() is False

    def test_model_info_returns_dict(self, mock_client: GemmaClient):
        """model_info() returns dict with expected keys."""
        mock_response = {
            "model_info": {"key": "value"},
            "details": {"quantization_level": "Q4_K_M"}
        }
        mock_client._client.show.return_value = mock_response
        info = mock_client.model_info()
        assert "model" in info
        assert "quantization" in info
        assert "num_ctx" in info
        assert "raw" in info

    def test_extract_text_sdk_object(self, mock_client: GemmaClient):
        """_extract_text_from_chat_response handles SDK ChatResponse object."""
        mock_response = MagicMock()
        mock_response.message.content = "test content"
        result = mock_client._extract_text_from_chat_response(mock_response)
        assert result == "test content"

    def test_extract_text_dict(self, mock_client: GemmaClient):
        """_extract_text_from_chat_response handles plain dict."""
        response = {"message": {"content": "dict content"}}
        result = mock_client._extract_text_from_chat_response(response)
        assert result == "dict content"

    def test_extract_text_empty_raises(self, mock_client: GemmaClient):
        """_extract_text_from_chat_response raises on empty content."""
        response = {"message": {"content": ""}}
        with pytest.raises(GemmaResponseError, match="empty or invalid content"):
            mock_client._extract_text_from_chat_response(response)


# ---------------------------------------------------------------------------
# Integration tests (require Ollama)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.getenv("SKIP_OLLAMA_TESTS", "true").lower() == "true",
    reason="Set SKIP_OLLAMA_TESTS=false to run Ollama integration tests"
)
class TestGemmaClientIntegration:
    """Integration tests requiring a running Ollama server."""

    def test_is_available_live(self, live_client: GemmaClient):
        """is_available() returns True with real Ollama."""
        assert live_client.is_available() is True

    def test_generate_returns_nonempty_string(self, live_client: GemmaClient):
        """generate() returns non-empty string."""
        result = live_client.generate("Say OK")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_generate_json_output(self, live_client: GemmaClient):
        """generate() returns parseable JSON."""
        result = live_client.generate('Return only JSON: {"ok": true}')
        clean_result = result.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(clean_result)
        assert parsed.get("ok") is True

    def test_think_returns_string(self, live_client: GemmaClient):
        """think() returns non-empty string."""
        result = live_client.think("Is nylon a polymer?")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_model_info_has_keys(self, live_client: GemmaClient):
        """model_info() returns dict with required keys."""
        info = live_client.model_info()
        assert "model" in info
        assert "quantization" in info
        assert "num_ctx" in info

    def test_analyze_image_returns_string(self, live_client: GemmaClient, red_png_image: Path):
        """analyze_image() returns string for red PNG."""
        result = live_client.analyze_image(red_png_image, "What color?")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_validate_on_init_raises_if_unavailable(self):
        """validate_on_init=True raises if Ollama unavailable."""
        with patch.object(GemmaClient, "is_available", return_value=False):
            with pytest.raises(GemmaConnectionError, match="Ollama server not reachable"):
                GemmaClient(validate_on_init=True)

    def test_model_info_quantization_detected(self, live_client: GemmaClient):
        """model_info() detects quantization (proves model loaded on CPU or GPU)."""
        info = live_client.model_info()
        assert info["quantization"] != "unknown"

    def test_generate_completes_within_timeout(self, live_client: GemmaClient):
        """generate() completes within timeout."""
        start = time.time()
        result = live_client.generate("Say OK")
        elapsed = time.time() - start
        assert elapsed < live_client.timeout
