"""
agents/base_agent.py — BaseAgent Abstract Class

All PassportAI agents inherit from BaseAgent. Provides:
  - Shared GemmaClient access
  - _parse_json_response() — strips markdown, parses JSON
  - _load_prompt() — loads prompt files from prompts/ directory
  - Abstract run() method that subclasses must implement

Usage:
    from agents.base_agent import BaseAgent

    class MyAgent(BaseAgent):
        def run(self, product_data: dict) -> dict:
            prompt = self._load_prompt("my_agent.txt")
            raw = self.client.generate(prompt.format(**product_data))
            return self._parse_json_response(raw)
"""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all PassportAI pipeline agents.

    Provides shared utilities for LLM interaction and JSON parsing.
    Subclasses implement the run() method with agent-specific logic.

    Attributes:
        client: GemmaClient instance shared across all agents.
        prompts_dir: Path to the prompts directory.
        name: Agent name (used in logging and error messages).
    """

    def __init__(
        self,
        client: Any,  # GemmaClient
        prompts_dir: Path | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize BaseAgent.

        Args:
            client: GemmaClient instance. Can be None for testing.
            prompts_dir: Path to prompts directory. Defaults to ./prompts.
            name: Human-readable agent name for logging.
        """
        self.client = client
        self.prompts_dir = prompts_dir or Path("prompts")
        self.name = name or self.__class__.__name__

    @abstractmethod
    def run(self, **kwargs) -> dict:
        """Execute the agent's main task.

        This method must be implemented by all subclasses.
        It should call self.client.generate() or self.client.think(),
        then call self._parse_json_response() on the result.

        Args:
            **kwargs: Agent-specific input parameters.

        Returns:
            Dictionary with agent-specific output fields.
            The dictionary must be JSON-serializable.

        Raises:
            ValueError: If the model returns invalid JSON after retries.
            RuntimeError: If the GemmaClient call fails.
        """
        ...

    def _parse_json_response(self, raw: str) -> dict:
        """Parse JSON from a LLM response, stripping markdown code fences.

        Handles these common model response formats:
          - Plain JSON: `{"key": "value"}`
          - Markdown JSON: ` ```json\n{"key": "value"}\n``` `
          - Markdown no lang: ` ```\n{"key": "value"}\n``` `
          - JSON with leading text: "Here is the result:\n{"key": "value"}`

        Args:
            raw: Raw string response from GemmaClient.generate() or .think().

        Returns:
            Parsed Python dictionary.

        Raises:
            ValueError: If valid JSON cannot be extracted from the response.

        Example:
            >>> agent = MyAgent(None)
            >>> result = agent._parse_json_response('```json\n{"ok": true}\n```')
            >>> assert result == {"ok": True}

            >>> result = agent._parse_json_response('{"key": "value"}')
            >>> assert result == {"key": "value"}
        """
        text = raw.strip()

        # Strategy 1: Try direct JSON parse (fastest, model returned clean JSON)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Strip markdown code fences ```json ... ``` or ``` ... ```
        code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find the first { ... } JSON object in the text
        # (handles models that prepend explanatory text)
        json_pattern = r"\{[\s\S]*\}"
        match = re.search(json_pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Strategy 4: Find the first [ ... ] JSON array
        json_array_pattern = r"\[[\s\S]*\]"
        match = re.search(json_array_pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"[{self.name}] Could not extract valid JSON from LLM response.\n"
            f"First 300 chars: {text[:300]}"
        )

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt template from the prompts directory.

        Args:
            filename: Filename within prompts/ directory (e.g., "vision_analysis.txt").

        Returns:
            Prompt template string.

        Raises:
            FileNotFoundError: If the prompt file does not exist.

        Example:
            >>> agent = MyAgent(client)
            >>> prompt_template = agent._load_prompt("my_agent.txt")
            >>> prompt = prompt_template.format(product_name="Tote Bag")
        """
        prompt_path = self.prompts_dir / filename
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"[{self.name}] Prompt file not found: {prompt_path}"
            )
        return prompt_path.read_text(encoding="utf-8")

    def _safe_generate(self, prompt: str, retries: int = 2) -> dict:
        """Generate a JSON response from the model with retry logic.

        Calls client.generate() and attempts to parse JSON.
        Retries on JSONDecodeError up to `retries` times.

        Args:
            prompt: The prompt string to send to the model.
            retries: Number of additional attempts on parse failure.

        Returns:
            Parsed dictionary from model response.

        Raises:
            ValueError: If all attempts fail to produce valid JSON.
            RuntimeError: If GemmaClient fails.
        """
        last_error = None
        for attempt in range(retries + 1):
            # TODO: use self.client.generate(prompt) when implemented
            # raw = self.client.generate(prompt)
            # try:
            #     return self._parse_json_response(raw)
            # except ValueError as e:
            #     last_error = e
            #     if attempt < retries:
            #         # Add stronger JSON instruction on retry
            #         prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no text."
            pass
        raise ValueError(f"[{self.name}] Failed to get valid JSON after {retries + 1} attempts: {last_error}")


if __name__ == "__main__":
    # Test _parse_json_response with various input formats
    class TestAgent(BaseAgent):
        def run(self, **kwargs) -> dict:
            return {}

    agent = TestAgent(None)

    # Test 1: Plain JSON
    result = agent._parse_json_response('{"ok": true, "score": 72}')
    assert result == {"ok": True, "score": 72}, f"Failed: {result}"
    print("Test 1 (plain JSON): OK")

    # Test 2: Markdown JSON block
    result = agent._parse_json_response('```json\n{"ok": true}\n```')
    assert result == {"ok": True}, f"Failed: {result}"
    print("Test 2 (markdown JSON block): OK")

    # Test 3: Markdown block without language tag
    result = agent._parse_json_response('```\n{"key": "value"}\n```')
    assert result == {"key": "value"}, f"Failed: {result}"
    print("Test 3 (markdown block no lang): OK")

    # Test 4: JSON with leading text
    result = agent._parse_json_response('Here is the analysis:\n{"result": "pass"}')
    assert result == {"result": "pass"}, f"Failed: {result}"
    print("Test 4 (JSON with leading text): OK")

    # Test 5: Invalid JSON should raise ValueError
    try:
        agent._parse_json_response("This is not JSON at all.")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("Test 5 (invalid JSON raises ValueError): OK")

    print("\nAll _parse_json_response tests passed!")
