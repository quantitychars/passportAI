"""
gemma_client.py — PassportAI

Client wrapper for local Ollama Gemma model calls used by PassportAI agents.

Example:
    >>> from src.core.gemma_client import GemmaClient
    >>> client = GemmaClient()
    >>> result = client.generate("Return one word: ok")

Part of PassportAI — EU Digital Product Passport Generator
License: CC-BY 4.0 | https://github.com/quantitychars/passportai
"""

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv

load_dotenv(override=False)

logger = logging.getLogger(__name__)


class GemmaClientError(RuntimeError):
    """Base exception for all GemmaClient errors."""


class GemmaConnectionError(GemmaClientError):
    """Ollama server is unreachable or not running."""


class GemmaResponseError(GemmaClientError):
    """Ollama returned an unexpected or empty response."""


class GemmaModelNotFoundError(GemmaClientError):
    """The requested model is not available in Ollama."""


__all__ = [
    "GemmaClient",
    "ChatMessage",
    "GemmaClientError",
    "GemmaConnectionError",
    "GemmaResponseError",
    "GemmaModelNotFoundError",
]


class _ChatMessageRequired(TypedDict):
    """Required fields present in every Ollama chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatMessage(_ChatMessageRequired, total=False):
    """Typed structure for a single Ollama chat message.

    Attributes:
        role: Speaker role - "system", "user", or "assistant". Required.
        content: Text content of the message. Required.
        images: Base64-encoded image strings for vision requests. Optional.
    """

    images: list[str]


class GemmaClient:
    """Ollama wrapper for gemma4:e4b.

    Provides text generation, reasoning, and vision (multimodal) capabilities.
    The Ollama server must be running before instantiating this class.

    Attributes:
        model: Ollama model identifier (e.g. "gemma4:e4b").
        host: Ollama server URL (e.g. "http://localhost:11434").
        timeout: Request timeout in seconds.
        num_ctx: Context window size in tokens (default 8192).
                 DPP JSON-LD output requires at least 4096.
    """

    DEFAULT_MODEL = "gemma4:e4b"
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_TIMEOUT = 120
    DEFAULT_NUM_CTX: int = 8192
    RETRY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 2.0
    RETRY_BACKOFF_FACTOR: float = 2.0
    MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: int | None = None,
        validate_on_init: bool = False,  # False for test/CI compatibility; set True in production
                                          # to fail fast on startup if Ollama is unreachable.
    ) -> None:
        """Initialize GemmaClient.

        Args:
            model: Ollama model name. Defaults to OLLAMA_MODEL env var or "gemma4:e4b".
            host: Ollama server URL. Defaults to OLLAMA_HOST env var or
                  "http://localhost:11434".
            timeout: Request timeout in seconds. Defaults to OLLAMA_TIMEOUT env var
                     or 120.
            validate_on_init: If True, raises GemmaConnectionError immediately
                              if the Ollama server is unreachable or the model
                              is not loaded. Defaults to False for test/CI compatibility;
                              consider True in production.

        Raises:
            ImportError: If the `ollama` package is not installed.
            ValueError: If timeout is not a positive integer.
            GemmaConnectionError: If validate_on_init=True and server is not available.
        """
        self.model = (
            model if model is not None else os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        )
        self.host = (
            host if host is not None else os.getenv("OLLAMA_HOST", self.DEFAULT_HOST)
        )
        if not self.model:
            self.model = self.DEFAULT_MODEL
            logger.warning("OLLAMA_MODEL is empty, falling back to %s", self.DEFAULT_MODEL)
        if not self.host:
            self.host = self.DEFAULT_HOST
            logger.warning("OLLAMA_HOST is empty, falling back to %s", self.DEFAULT_HOST)

        self.timeout = (
            timeout
            if timeout is not None
            else int(os.getenv("OLLAMA_TIMEOUT", str(self.DEFAULT_TIMEOUT)))
        )
        if self.timeout <= 0:
            raise ValueError("timeout must be a positive integer")

        try:
            import ollama
        except ImportError as exc:
            logger.error("Failed to import ollama package: %s", exc)
            raise ImportError(
                "The 'ollama' package is required. Install it via 'pip install ollama'."
            ) from exc

        self._ollama = ollama
        self._httpx: Any = None
        try:
            import httpx as _httpx
            self._httpx = _httpx
        except ImportError:
            logger.warning("httpx not available; HTTP connection errors won't be retried")

        self._client = ollama.Client(host=self.host, timeout=self.timeout)

        if validate_on_init:
            if not self.is_available():
                raise GemmaConnectionError(
                    f"Ollama server not reachable at {self.host} "
                    f"or model '{self.model}' not loaded. "
                    f"Run: ollama serve && ollama pull {self.model}"
                )
            logger.info("GemmaClient validated: model=%s host=%s", self.model, self.host)

    def _extract_text_from_chat_response(self, response: Any) -> str:
        """Extract text content from an Ollama chat response.

        Handles both ollama.ChatResponse objects (SDK >= 0.2) and plain dicts
        for forward/backward compatibility.

        Args:
            response: Response returned by ollama.Client.chat().

        Returns:
            str: Assistant message text, stripped of whitespace.

        Raises:
            GemmaResponseError: If response does not contain non-empty string content.
        """
        if hasattr(response, "message"):
            content: Any = getattr(response.message, "content", None)
        elif isinstance(response, dict):
            message: Any = response.get("message", {})
            content = message.get("content") if isinstance(message, dict) else None
        else:
            raise GemmaResponseError(f"Unexpected Ollama response type: {type(response)!r}")

        if not isinstance(content, str) or not content.strip():
            raise GemmaResponseError(
                f"Ollama returned empty or invalid content: {response!r}"
            )

        return content.strip()

    def _process_chat_response(self, response: Any) -> str | dict:
        """Process Ollama chat response - check for tool calls or extract text.

        Checks for native tool_calls first (Ollama SDK >= 0.2 with function calling).
        Falls back to extracting plain text if no tool calls are present.

        Args:
            response: Response from ollama.Client.chat().

        Returns:
            dict: Parsed arguments from first tool call if native tool calling is used.
            str: Extracted text content if no tool calls are present.

        Raises:
            GemmaResponseError: If response is malformed.
        """
        # Path 1: Check for native tool_calls (Ollama SDK >= 0.2 + model supports tool use)
        if hasattr(response, "message") and hasattr(response.message, "tool_calls"):
            tool_calls = response.message.tool_calls
            if tool_calls:
                first_call = tool_calls[0]
                if hasattr(first_call, "function") and hasattr(first_call.function, "arguments"):
                    logger.info("_process_chat_response: native tool_calls path used")
                    return dict(first_call.function.arguments)

        # Path 2: Extract and return text
        return self._extract_text_from_chat_response(response)

    def _chat_with_retry(
        self,
        messages: list[ChatMessage],
        options: dict[str, Any],
        tools: list[dict] | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> str | dict:
        """Call Ollama chat API with retry logic and exponential backoff.

        Args:
            messages: Chat messages in Ollama format.
            options: Ollama options dict passed directly to client.chat().
            tools: Optional list of tool definitions for function calling.

        Returns:
            str: Assistant response text (for normal chat).
            dict: Parsed tool call arguments (if tools parameter was provided
                  and native tool calling is used).

        Raises:
            GemmaConnectionError: If server is unreachable after retries.
            GemmaResponseError: If response is malformed after retries.
        """
        last_error: Exception | None = None

        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            try:
                merged_options: dict[str, Any] = {
                    "num_ctx": self.DEFAULT_NUM_CTX,
                    **options,
                }
                chat_kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "options": merged_options,
                }
                if tools is not None:
                    chat_kwargs["tools"] = tools

                if response_format is not None:
                    chat_kwargs["format"] = response_format

                response: Any = self._client.chat(**chat_kwargs)
                return self._process_chat_response(response)
            except self._ollama.ResponseError as exc:
                last_error = exc
                logger.warning(
                    "Ollama response error on attempt %s/%s: %s",
                    attempt, self.RETRY_ATTEMPTS, exc,
                )
            except (ValueError, KeyError, TypeError) as exc:
                last_error = exc
                logger.warning(
                    "Invalid Ollama payload on attempt %s/%s: %s",
                    attempt, self.RETRY_ATTEMPTS, exc,
                )
            except Exception as exc:
                if self._httpx and isinstance(exc, self._httpx.HTTPError):
                    last_error = exc
                    logger.warning(
                        "HTTP connection error on attempt %d/%d: %s",
                        attempt, self.RETRY_ATTEMPTS, exc,
                    )
                else:
                    logger.error("Unrecoverable error in _chat_with_retry: %s", exc)
                    raise

            if attempt < self.RETRY_ATTEMPTS:
                delay = self.RETRY_DELAY_SECONDS * (
                    self.RETRY_BACKOFF_FACTOR ** (attempt - 1)
                )
                logger.debug(
                    "Retrying in %.1f seconds (attempt %d/%d)",
                    delay, attempt, self.RETRY_ATTEMPTS,
                )
                time.sleep(delay)

        if self._httpx and isinstance(last_error, self._httpx.HTTPError):
            raise GemmaConnectionError(
                f"Cannot connect to Ollama at {self.host} after {self.RETRY_ATTEMPTS} attempts"
            ) from last_error

        # Fallback: detect connection errors by message when httpx is unavailable
        if last_error is not None:
            err_msg = str(last_error).lower()
            if any(k in err_msg for k in ("connection", "refused", "unreachable", "timeout", "connect")):
                raise GemmaConnectionError(
                    f"Cannot connect to Ollama at {self.host} after {self.RETRY_ATTEMPTS} attempts"
                ) from last_error

        raise GemmaResponseError(
            f"Ollama returned invalid response after {self.RETRY_ATTEMPTS} attempts"
        ) from last_error

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        """Generate a text response from a prompt.

        Args:
            prompt: The input prompt string.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).

        Returns:
            The model's response as a string.

        Raises:
            ValueError: If prompt is empty.
            GemmaConnectionError: If Ollama server is unreachable.
            GemmaResponseError: If response is malformed.

        Example:
            >>> client = GemmaClient()
            >>> response = client.generate("List 3 EU sustainability regulations")
        """
        clean_prompt: str = prompt.strip()
        if not clean_prompt:
            raise ValueError("prompt must not be empty")

        logger.info("Generating text with model=%s", self.model)
        messages: list[ChatMessage] = [ChatMessage(role="user", content=clean_prompt)]
        return self._chat_with_retry(
            messages=messages,
            options={"temperature": temperature},
        )

    def think(self, prompt: str) -> str:
        """Generate a response using extended reasoning (thinking) mode.

        Activates chain-of-thought reasoning via options={"think": True}.
        Useful for complex compliance analysis (REACH, ESPR classification, etc.).

        Args:
            prompt: The input prompt.

        Returns:
            The model's final answer string.

        Raises:
            ValueError: If prompt is empty.
            GemmaConnectionError: If Ollama server is unreachable.

        Example:
            >>> client = GemmaClient()
            >>> answer = client.think("Is REACH Article 33 applicable to nylon bags?")
        """
        clean_prompt: str = prompt.strip()
        if not clean_prompt:
            raise ValueError("prompt must not be empty")

        logger.info("Running think-mode with model=%s", self.model)
        messages: list[ChatMessage] = [ChatMessage(role="user", content=clean_prompt)]
        return self._chat_with_retry(
            messages=messages,
            options={"temperature": 0.1, "think": True},
        )

    def analyze_image(self, image_path: str | Path, prompt: str) -> str:
        """Analyze an image using Gemma 4's vision capabilities.

        Args:
            image_path: Path to the image file (JPEG, PNG, WebP supported).
            prompt: Instruction for what to analyze in the image.

        Returns:
            Text description/analysis from the model.

        Raises:
            FileNotFoundError: If image_path does not exist.
            ValueError: If image file exceeds 10 MB or prompt is empty.
            GemmaClientError: If file cannot be read.

        Example:
            >>> client = GemmaClient()
            >>> result = client.analyze_image("product.jpg", "List all visible materials")
        """
        image_file: Path = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"Image not found: {image_file}")

        file_size: int = image_file.stat().st_size
        if file_size > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image file too large: {file_size / 1_048_576:.1f} MB "
                f"(max {self.MAX_IMAGE_SIZE_BYTES // 1_048_576} MB)."
            )

        clean_prompt: str = prompt.strip()
        if not clean_prompt:
            raise ValueError("prompt must not be empty")

        logger.info("Analyzing image with model=%s file=%s", self.model, image_file.name)
        try:
            image_data: str = base64.b64encode(image_file.read_bytes()).decode("utf-8")
        except OSError as exc:
            raise GemmaClientError(f"Failed to read image file {image_file}: {exc}") from exc

        messages: list[ChatMessage] = [
            ChatMessage(role="user", content=clean_prompt, images=[image_data])
        ]
        vision_response_schema: dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "textiles",
                        "batteries",
                        "electrical_appliances",
                        "unknown",
                    ],
                },
                "product_type": {
                    "type": "string",
                },
                "materials": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "certifications_visible": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "special_markings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "required": [
                "category",
                "product_type",
                "materials",
                "colors",
                "certifications_visible",
                "special_markings",
                "confidence",
            ],
        }

        return self._chat_with_retry(
            messages=messages,
            options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 900,
            },
            response_format=vision_response_schema,
        )

    def call_tool(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict:
        """Call Gemma 4 with native function calling via Ollama tools= parameter.

        Attempts native tool calling first (Ollama returns tool_calls object).
        Falls back to _parse_json_fallback() if model returns plain text instead.
        This makes the method safe regardless of Ollama SDK version.

        Args:
            prompt: User prompt describing the task.
            tools: List of tool definitions in OpenAI function calling format.
                   Each tool must have: type="function", function.name,
                   function.description, function.parameters (JSON Schema).
            system_prompt: Optional system role message prepended to conversation.

        Returns:
            dict: Parsed arguments from the first tool call, or parsed JSON
                  from text response if native tool calling is unavailable.

        Raises:
            ValueError: If prompt is empty.
            GemmaConnectionError: If Ollama server is unreachable after retries.
            GemmaResponseError: If response cannot be parsed after retries.

        Example:
            >>> result = client.call_tool(
            ...     prompt="Product: cotton tote bag, made in Ukraine",
            ...     tools=[{
            ...         "type": "function",
            ...         "function": {
            ...             "name": "extract_product",
            ...             "description": "Extract product attributes",
            ...             "parameters": {
            ...                 "type": "object",
            ...                 "properties": {
            ...                     "category": {"type": "string"},
            ...                     "materials": {"type": "array", "items": {"type": "string"}}
            ...                 },
            ...                 "required": ["category", "materials"]
            ...             }
            ...         }
            ...     }]
            ... )
            >>> assert "materials" in result
        """
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("prompt must not be empty")

        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=clean_prompt))

        tool_names = [t.get("function", {}).get("name", "?") for t in tools]
        logger.info("call_tool: model=%s tools=%s", self.model, tool_names)

        result = self._chat_with_retry(
            messages=messages,
            options={"temperature": 0.1},
            tools=tools,
        )

        # If we got a dict from native tool_calls, return it
        if isinstance(result, dict):
            return result

        # Otherwise, parse the text response as JSON (fallback)
        logger.info("call_tool: received text response, using _parse_json_fallback")
        return self._parse_json_fallback(result)

    def _parse_json_fallback(self, raw: str) -> dict:
        """Parse JSON from plain text model response.

        Used as fallback in call_tool() when the model returns text instead
        of a native tool_calls object. Strips markdown code fences before parsing.

        Args:
            raw: Raw text string from model response, possibly wrapped in
                 markdown code fences (```json ... ``` or ``` ... ```).

        Returns:
            dict: Parsed JSON object.

        Raises:
            GemmaResponseError: If the text cannot be parsed as valid JSON
                                after stripping markdown fences.

        Example:
            >>> result = client._parse_json_fallback('```json\n{"ok": true}\n```')
            >>> assert result == {"ok": True}
        """
        # Strip markdown code fences first
        cleaned = re.sub(r"^```[^\n]*\n?", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)

        # Try to extract the first JSON object or array
        match = re.search(r"[\[{].*[\]}]", cleaned.strip(), re.DOTALL)
        if match:
            cleaned = match.group()

        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as exc:
            raise GemmaResponseError(
                f"Model returned invalid JSON (first 200 chars): {raw[:200]!r}"
            ) from exc

    def model_info(self) -> dict[str, Any]:
        """Return runtime information about the loaded model.

        Returns:
            dict containing "model", "quantization", "num_ctx", "raw".
            On failure, returns {"model": ..., "error": <message>}.

        Example:
            >>> info = client.model_info()
            >>> if info.get("quantization") == "unknown":
            ...     logger.warning("Could not detect quantization level")
            >>> if "error" in info:
            ...     logger.error("Model info unavailable: %s", info["error"])
        """
        try:
            response: Any = self._client.show(model=self.model)

            if hasattr(response, "model_info"):
                raw: Any = response.model_info
            elif isinstance(response, dict):
                raw = response.get("model_info", {})
            else:
                raw = {}

            details: Any = getattr(response, "details", None) or (
                response.get("details", {}) if isinstance(response, dict) else {}
            )
            quantization: str = getattr(details, "quantization_level", None) or (
                details.get("quantization_level", "unknown")
                if isinstance(details, dict)
                else "unknown"
            )

            info: dict[str, Any] = {
                "model": self.model,
                "quantization": quantization,
                "num_ctx": self.DEFAULT_NUM_CTX,
                "raw": raw,
            }

            logger.info("Model %s quantization=%s", self.model, quantization)
            return info

        except self._ollama.ResponseError as exc:
            logger.warning("Could not fetch model info: %s", exc)
            return {"model": self.model, "error": str(exc)}
        except Exception as exc:
            logger.error("Unexpected error in model_info(): %s", exc)
            return {"model": self.model, "error": str(exc)}

    def is_available(self) -> bool:
        """Check if the Ollama server is running and the model is loaded.

        Returns:
            True if the server is reachable and the model is available.

        Example:
            >>> if not client.is_available():
            ...     print("Run: ollama serve && ollama pull gemma4:e4b")
        """
        try:
            list_response: Any = self._client.list()

            if hasattr(list_response, "models"):
                raw_models: Any = list_response.models
            elif isinstance(list_response, dict):
                raw_models = list_response.get("models", [])
            else:
                logger.warning("Unexpected list() response type: %s", type(list_response))
                return False

            if not isinstance(raw_models, list):
                logger.warning("Unexpected 'models' payload: %s", raw_models)
                return False

            model_names: set[str] = set()
            for m in raw_models:
                if m is None:
                    continue
                name: str | None = getattr(m, "model", None) or (
                    m.get("model") or m.get("name") if isinstance(m, dict) else None
                )
                if isinstance(name, str) and name:
                    model_names.add(name)

            return any(
                name == self.model or name.startswith(f"{self.model}:")
                for name in model_names
                if name
            )
        except self._ollama.ResponseError as exc:
            logger.warning("Ollama unavailable: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error in is_available(): %s", exc)
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = GemmaClient()
    logger.info("Model: %s", client.model)
    logger.info("Host: %s", client.host)
    logger.info("Available: %s", client.is_available())
