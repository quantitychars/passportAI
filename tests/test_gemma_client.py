"""
tests/test_gemma_client.py — Tests for GemmaClient

Tests:
    - Initialization with default and custom parameters
    - generate() method (requires Ollama — skipped if not available)
    - analyze_image() method (requires Ollama — skipped if not available)
    - is_available() health check

Run:
    pytest tests/test_gemma_client.py -v
    pytest tests/test_gemma_client.py -v -k "not ollama"  # skip Ollama tests
"""

import os
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client_config():
    """Default GemmaClient configuration for tests."""
    return {
        "model": "gemma4:12b-q4_k_m",
        "host": "http://localhost:11434",
        "timeout": 30,
    }


@pytest.fixture
def mock_image(tmp_path):
    """Create a small test PNG image."""
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img_path = tmp_path / "test_image.png"
        img.save(str(img_path))
        return img_path
    except ImportError:
        pytest.skip("Pillow not installed")


# ---------------------------------------------------------------------------
# Unit tests (no Ollama needed)
# ---------------------------------------------------------------------------

class TestGemmaClientInit:
    """Test GemmaClient initialization."""

    def test_default_initialization(self):
        """GemmaClient initializes with default values from env vars."""
        # TODO: implement after GemmaClient is complete
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # assert client.model == os.getenv("OLLAMA_MODEL", "gemma4:12b-q4_k_m")
        # assert client.host == os.getenv("OLLAMA_HOST", "http://localhost:11434")
        pytest.skip("GemmaClient not yet implemented")

    def test_custom_initialization(self, client_config):
        """GemmaClient accepts custom model, host, and timeout."""
        # TODO: implement after GemmaClient is complete
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient(**client_config)
        # assert client.model == client_config["model"]
        # assert client.host == client_config["host"]
        # assert client.timeout == client_config["timeout"]
        pytest.skip("GemmaClient not yet implemented")

    def test_model_from_env(self, monkeypatch):
        """GemmaClient reads model name from OLLAMA_MODEL env var."""
        # monkeypatch.setenv("OLLAMA_MODEL", "gemma4:2b")
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # assert client.model == "gemma4:2b"
        pytest.skip("GemmaClient not yet implemented")

    def test_missing_image_raises(self, tmp_path):
        """analyze_image() raises FileNotFoundError for missing image."""
        # TODO: implement after GemmaClient is complete
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # with pytest.raises(FileNotFoundError):
        #     client.analyze_image(tmp_path / "nonexistent.jpg", "test")
        pytest.skip("GemmaClient not yet implemented")


# ---------------------------------------------------------------------------
# Integration tests (require Ollama)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.getenv("SKIP_OLLAMA_TESTS", "true").lower() == "true",
    reason="Set SKIP_OLLAMA_TESTS=false to run Ollama integration tests"
)
class TestGemmaClientOllama:
    """Integration tests that require a running Ollama server."""

    def test_is_available(self):
        """is_available() returns True when Ollama is running."""
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # assert client.is_available() is True
        pytest.skip("GemmaClient not yet implemented")

    def test_generate_returns_string(self):
        """generate() returns a non-empty string."""
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # result = client.generate("Say 'OK' in one word")
        # assert isinstance(result, str)
        # assert len(result) > 0
        pytest.skip("GemmaClient not yet implemented")

    def test_generate_json_output(self):
        """generate() can produce valid JSON when asked."""
        # import json
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # result = client.generate('Return only this JSON: {"ok": true}')
        # # Strip markdown if present
        # clean = result.strip().strip("```json").strip("```").strip()
        # parsed = json.loads(clean)
        # assert parsed.get("ok") is True
        pytest.skip("GemmaClient not yet implemented")

    def test_analyze_image_returns_string(self, mock_image):
        """analyze_image() returns a non-empty string."""
        # from src.core.gemma_client import GemmaClient
        # client = GemmaClient()
        # result = client.analyze_image(mock_image, "What color is this image?")
        # assert isinstance(result, str)
        # assert len(result) > 0
        pytest.skip("GemmaClient not yet implemented")
