"""
src/core/gemma_client.py — Ollama/Gemma 4 Client

Wraps the Ollama Python SDK to provide a clean interface for:
  - Text generation (generate)
  - Thinking/reasoning mode (think)
  - Multimodal image analysis (analyze_image)

All methods are synchronous. The model runs 100% locally via Ollama.

Model: gemma4:e4b (configured via OLLAMA_MODEL env var)
Server: http://localhost:11434 (configured via OLLAMA_HOST env var)

Usage:
    client = GemmaClient()
    text = client.generate("Describe this product")
    text = client.analyze_image("photo.jpg", "List materials visible")
"""

import base64
import os
from pathlib import Path


class GemmaClient:
    """Ollama wrapper for Gemma 4 12B Q4_K_M.

    Provides text generation, reasoning, and vision (multimodal) capabilities.
    The Ollama server must be running before instantiating this class.

    Attributes:
        model: Ollama model identifier (e.g. "gemma4:e4b").
        host: Ollama server URL (e.g. "http://localhost:11434").
        timeout: Request timeout in seconds.
    """

    DEFAULT_MODEL = "gemma4:e4b"
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_TIMEOUT = 120

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize GemmaClient.

        Args:
            model: Ollama model name. Defaults to OLLAMA_MODEL env var or
                   "gemma4:e4b".
            host: Ollama server URL. Defaults to OLLAMA_HOST env var or
                  "http://localhost:11434".
            timeout: Request timeout in seconds. Defaults to OLLAMA_TIMEOUT env var
                     or 120.
        """
        self.model = model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self.host = host or os.getenv("OLLAMA_HOST", self.DEFAULT_HOST)
        self.timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", self.DEFAULT_TIMEOUT))

        # TODO: initialize ollama client
        # import ollama
        # self._client = ollama.Client(host=self.host)
        self._client = None  # Replace with real client

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        """Generate a text response from a prompt.

        Args:
            prompt: The input prompt string.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
                         Lower values produce more consistent JSON output.

        Returns:
            The model's response as a string.

        Raises:
            RuntimeError: If Ollama server is unreachable or returns an error.

        Example:
            >>> client = GemmaClient()
            >>> response = client.generate("List 3 EU sustainability regulations")
            >>> print(response)
        """
        # TODO: implement text generation
        # try:
        #     response = self._client.generate(
        #         model=self.model,
        #         prompt=prompt,
        #         options={"temperature": temperature},
        #     )
        #     return response["response"]
        # except Exception as e:
        #     raise RuntimeError(f"Ollama generate failed: {e}") from e
        raise NotImplementedError("GemmaClient.generate() not yet implemented")

    def think(self, prompt: str) -> str:
        """Generate a response using extended reasoning (thinking) mode.

        Thinking mode inserts a <think>...</think> block before the final answer,
        allowing the model to reason step-by-step before producing output.
        Useful for complex compliance analysis.

        Args:
            prompt: The input prompt. Should ask for structured reasoning.

        Returns:
            The model's final answer (after the </think> block).

        Raises:
            RuntimeError: If Ollama server is unreachable or returns an error.

        Example:
            >>> client = GemmaClient()
            >>> answer = client.think("Is REACH Article 33 applicable to nylon bags?")
        """
        # TODO: implement thinking mode
        # The thinking prompt wraps the user prompt to enable chain-of-thought
        # think_prompt = f"<think>\n{prompt}\n</think>\nFinal answer:"
        # raw = self.generate(think_prompt, temperature=0.1)
        # # Strip the think block if model includes it in output
        # if "</think>" in raw:
        #     return raw.split("</think>")[-1].strip()
        # return raw
        raise NotImplementedError("GemmaClient.think() not yet implemented")

    def analyze_image(self, image_path: str | Path, prompt: str) -> str:
        """Analyze an image using Gemma 4's vision capabilities.

        Sends the image to Ollama as a base64-encoded attachment.
        Gemma 4 12B supports multimodal input natively.

        Args:
            image_path: Path to the image file (JPEG, PNG, WebP supported).
            prompt: Instruction for what to analyze in the image.

        Returns:
            Text description/analysis from the model.

        Raises:
            FileNotFoundError: If image_path does not exist.
            RuntimeError: If Ollama returns an error.

        Example:
            >>> client = GemmaClient()
            >>> result = client.analyze_image("product.jpg", "List all visible materials")
            >>> print(result)

        Note:
            Uses Ollama's `images` parameter for multimodal requests.
            The image is passed as a base64-encoded string, NOT a URL.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # TODO: implement image analysis
        # with open(image_path, "rb") as f:
        #     image_data = base64.b64encode(f.read()).decode("utf-8")
        #
        # try:
        #     response = self._client.generate(
        #         model=self.model,
        #         prompt=prompt,
        #         images=[image_data],
        #         options={"temperature": 0.2},
        #     )
        #     return response["response"]
        # except Exception as e:
        #     raise RuntimeError(f"Ollama analyze_image failed: {e}") from e
        raise NotImplementedError("GemmaClient.analyze_image() not yet implemented")

    def is_available(self) -> bool:
        """Check if the Ollama server is running and the model is loaded.

        Returns:
            True if the server is reachable and the model is available.

        Example:
            >>> client = GemmaClient()
            >>> if not client.is_available():
            ...     print("Run: ollama serve && ollama pull gemma4:e4b")
        """
        # TODO: implement health check
        # try:
        #     models = self._client.list()
        #     model_names = [m["name"] for m in models.get("models", [])]
        #     return self.model in model_names
        # except Exception:
        #     return False
        raise NotImplementedError("GemmaClient.is_available() not yet implemented")


if __name__ == "__main__":
    # Quick connectivity test
    client = GemmaClient()
    print(f"Model: {client.model}")
    print(f"Host:  {client.host}")
    # TODO: uncomment after implementation
    # available = client.is_available()
    # print(f"Available: {available}")
    # if available:
    #     response = client.generate("Say 'OK' in exactly one word")
    #     print(f"Response: {response}")
