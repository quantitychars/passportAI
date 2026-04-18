# PassportAI — GitHub Copilot Instructions

## Project Overview
PassportAI generates ESPR-compliant EU Digital Product Passports (DPP) from a product photo
and description using Gemma 4 12B Q4_K_M via Ollama, running 100% offline.
See COPILOT_CONTEXT.md for full architecture reference.

---

## Code Quality Rules (STRICT — never shortcut these)

### 1. No placeholder implementations
NEVER write:
```python
def generate(self, prompt: str) -> str:
    # TODO: implement
    pass
```
ALWAYS write complete, working implementation or raise NotImplementedError with a message:
```python
def generate(self, prompt: str) -> str:
    raise NotImplementedError("Call ollama.chat() with self.model and return response text")
```

### 2. Type hints are mandatory — everywhere
```python
# WRONG
def extract_attributes(image_path, description):

# CORRECT
def extract_attributes(self, image_path: str | Path, description: str) -> dict[str, Any]:
```

### 3. Every method has a docstring with Args, Returns, Raises
```python
def generate_from_text(self, description: str) -> dict:
    """
    Generate a JSON-LD DPP passport from a text description.

    Args:
        description: Natural language product description (1-3 sentences minimum)

    Returns:
        dict: Valid JSON-LD VCDM 2.0 passport matching DPP_SCHEMA.json structure

    Raises:
        OllamaConnectionError: If Ollama server is not running on localhost:11434
        JSONParseError: If Gemma 4 returns malformed JSON after 3 retry attempts
    """
```

### 4. No silent failures — always explicit error handling
```python
# WRONG
try:
    result = ollama.chat(...)
except:
    return {}

# CORRECT
try:
    result = ollama.chat(model=self.model, messages=messages)
except ollama.ResponseError as e:
    logger.error(f"Ollama API error: {e}")
    raise OllamaConnectionError(f"Model {self.model} failed: {e}") from e
except Exception as e:
    logger.error(f"Unexpected error in generate(): {e}")
    raise
```

### 5. Retry logic for all LLM calls
Gemma 4 occasionally returns malformed JSON. Always implement retry:
```python
MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    response = self.client.generate(prompt)
    parsed = self._parse_json_response(response)
    if parsed:
        return parsed
    logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES}: invalid JSON, retrying...")

raise JSONParseError(f"Failed to get valid JSON after {MAX_RETRIES} attempts")
```

### 6. Logging over print statements
```python
# WRONG
print(f"Generated passport for {product_name}")

# CORRECT
import logging
logger = logging.getLogger(__name__)
logger.info(f"Generated passport for {product_name} (id={passport_id})")
```

### 7. pathlib.Path for ALL file operations — never raw strings
```python
# WRONG
open("output/" + uuid + "/passport.json", "w")

# CORRECT
from pathlib import Path
output_dir = Path("output") / passport_id
output_dir.mkdir(parents=True, exist_ok=True)
passport_file = output_dir / "passport.json"
passport_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

### 8. Environment variables via python-dotenv — never hardcode
```python
# WRONG
model = "gemma4:e4b"
bucket = "passportai-dpp"

# CORRECT
from dotenv import load_dotenv
load_dotenv()
model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
bucket = os.getenv("S3_BUCKET", "passportai-dpp")
```

### 9. Dataclasses or TypedDict for all structured data — no raw dicts
```python
# WRONG
def run(self, product_data: dict) -> dict:

# CORRECT
from dataclasses import dataclass

@dataclass
class ProductInput:
    image_path: str
    description: str
    gtin: str | None = None
    certificates: list[str] = field(default_factory=list)
    storage_mode: str = "local"

def run(self, product_data: ProductInput) -> PassportPackage:
```

### 10. Every module has __all__ and module-level logger
```python
"""
Module docstring here.
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ["ClassName", "function_name"]
```

---

## Agent-Specific Rules

### All agents extend BaseAgent
```python
from agents.base_agent import BaseAgent

class RegulatoryConsultantAgent(BaseAgent):
    # NEVER duplicate _parse_json_response() — it lives in BaseAgent only
```

### Agent run() method signature is fixed
```python
def run(self, input_data: dict) -> dict:
    """Always returns dict with 'success': bool and 'data': dict keys"""
    try:
        result = self._do_work(input_data)
        return {"success": True, "data": result, "agent": self.name}
    except Exception as e:
        logger.error(f"{self.name} failed: {e}")
        return {"success": False, "error": str(e), "agent": self.name}
```

### Prompts are loaded from files — never hardcoded in Python
```python
# WRONG
prompt = f"Generate DPP for {description}. Return JSON."

# CORRECT
from pathlib import Path
PROMPT_DIR = Path("prompts")

def _load_prompt(self, name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")

prompt = self._load_prompt("dpp_generation").format(
    description=description,
    category=category
)
```

---

## Testing Rules

### Every public method has at least one test
```python
# Minimum test structure for every method:
def test_method_name_happy_path():
    """Test normal operation"""

def test_method_name_invalid_input():
    """Test with bad input"""

def test_method_name_edge_case():
    """Test boundary condition"""
```

### Mock Ollama in tests — never call real model in unit tests
```python
from unittest.mock import patch, MagicMock

@patch("src.core.gemma_client.ollama.chat")
def test_generate_returns_string(mock_chat):
    mock_chat.return_value = {"message": {"content": "test response"}}
    client = GemmaClient()
    result = client.generate("test prompt")
    assert isinstance(result, str)
    assert result == "test response"
```

### Use fixtures for test data
```python
# tests/conftest.py
import pytest
import json
from pathlib import Path

@pytest.fixture
def sample_passport():
    return json.loads((Path("tests/fixtures/sample_product.json")).read_text())

@pytest.fixture
def gemma_client():
    return GemmaClient(model="gemma4:e4b")
```

---

## What Copilot Should NEVER Do

1. **Never truncate implementations** with "# ... rest of implementation" or "# similar to above"
2. **Never use `Any` type without importing** from typing
3. **Never write bare `except:`** — always catch specific exceptions
4. **Never use mutable default arguments** `def func(items=[]):`
5. **Never skip the retry loop** for LLM calls
6. **Never generate QR before storage** — QR needs URL, URL needs storage
7. **Never fetch JSON-LD contexts at runtime** — use cached files in contexts/
8. **Never store credentials in code** — only via .env

---

## File Header Template
Every Python file must start with:
```python
"""
<module_name>.py — PassportAI

<One sentence: what this module does>

Example:
    >>> from src.core.gemma_client import GemmaClient
    >>> client = GemmaClient()
    >>> result = client.generate("test")

Part of PassportAI — EU Digital Product Passport Generator
License: CC-BY 4.0 | https://github.com/yourusername/passportai
"""
```
