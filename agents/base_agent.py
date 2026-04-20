"""
agents/base_agent.py — PassportAI

The foundational abstract class for the multi-agent pipeline.
Ensures standardized output via AgentResult and provides double-phase
verification (think-then-tool) to eliminate hallucinations.

Part of PassportAI — EU Digital Product Passport Generator
License: CC-BY 4.0
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from src.core.gemma_client import GemmaClient

__all__ = ["BaseAgent", "AgentSuccessResult", "AgentErrorResult", "AgentResult", "SourceType", "ConfidenceType", "Evidence"]

logger = logging.getLogger(__name__)

# Куда ссылаемся (Origin)
SourceType = Literal[
    "internal_csv",
    "regulation_text",
    "visual_analysis",
    "user_input",
    "llm_knowledge",
]

# Насколько уверены (Reliability)
ConfidenceType = Literal[
    "lookup_table",
    "regulation_text",
    "model_estimate",
    "insufficient_data",
]


class Evidence(TypedDict):
    """Typed representation of the evidence block required in all regulatory tool schemas."""
    source_type: SourceType
    confidence: ConfidenceType
    reasoning_summary: str


class AgentSuccessResult(TypedDict):
    success: Literal[True]
    data: dict[str, Any]
    agent: str
    is_mock: bool

class AgentErrorResult(TypedDict):
    success: Literal[False]
    error: str
    agent: str
    is_mock: bool

AgentResult = AgentSuccessResult | AgentErrorResult


class BaseAgent(ABC):
    """Abstract base class for all PassportAI agents.

    Provides:
    - Standard __init__ with optional GemmaClient (None allowed for mocks/tests)
    - Abstract run() — each agent implements its own pipeline step
    - call_tool() shortcut — single-phase, delegates to GemmaClient.call_tool()
    - run_verified_task() — two-phase think→call_tool anti-hallucination protocol
    - think() delegate — extended reasoning via GemmaClient.think()
    - _load_prompt() — loads prompt text from prompts/{name}.txt via pathlib
    - _format_success() / _format_error() — typed AgentResult constructors

    Subclass contract:
        class MyAgent(BaseAgent):
            def run(self, *, some_input: str) -> AgentResult:
                try:
                    data = self.call_tool(prompt, MY_TOOL)
                    return self._format_success(data)
                except SomeSpecificError as exc:
                    return self._format_error(exc)

    Which GemmaClient method to use per agent:
        VisionAgent          → call_tool()          (visual facts, no regulatory hallucination risk)
        DPPGenerator         → call_tool()          (generation from schema, temperature 0.1)
        RegulatoryConsultant → run_verified_task()  (ESPR dates 2026/2027/2030 — critical)
        LegalAgent           → run_verified_task()  (REACH SVHC, RoHS — false flag worse than missing)
        LCASpecialist        → call_tool() + CSV    (GWP from lookup table, never from LLM)
        DataAuditAgent       → deterministic Python (dict comparison, no LLM)
        GS1Specialist        → call_tool()          (GTIN + DID — deterministic math)
    """

    # Override to True in mock/stub agents for Gradio ⚠️ indicator
    IS_MOCK: bool = False

    # Shared Evidence schema — inject into tool definitions of regulatory agents.
    # reasoning_summary is in required[] intentionally: if optional, the model skips it.
    # An empty string "" is acceptable — absence of the field is not.
    EVIDENCE_SCHEMA: Final[dict[str, Any]] = {
        "evidence": {
            "type": "object",
            "description": (
                "Source and confidence of this output. "
                "Required for ESPR audit trail. "
                "reasoning_summary may be empty string but must be present."
            ),
            "properties": {
                "source_type": {
                    "type": "string",
                    "description": (
                        "Where this data comes from. "
                        "internal_csv = gwp_coefficients.csv lookup, "
                        "regulation_text = ESPR/REACH/RoHS official source, "
                        "visual_analysis = image inspection, "
                        "user_input = form field provided by user, "
                        "llm_knowledge = model training data (lowest trust)"
                    ),
                    "enum": [
                        "internal_csv",
                        "regulation_text",
                        "visual_analysis",
                        "user_input",
                        "llm_knowledge",
                    ],
                },
                "confidence": {
                    "type": "string",
                    "description": (
                        "Reliability level. "
                        "lookup_table = exact CSV match, "
                        "regulation_text = cited from official regulation, "
                        "model_estimate = model inference (verify before use), "
                        "insufficient_data = not enough information to answer"
                    ),
                    "enum": [
                        "lookup_table",
                        "regulation_text",
                        "model_estimate",
                        "insufficient_data",
                    ],
                },
                "reasoning_summary": {
                    "type": "string",
                    "description": (
                        "Brief explanation of why this classification was chosen. "
                        "Use empty string '' if not applicable. "
                        "Do NOT leave this field absent."
                    ),
                },
            },
            "required": ["source_type", "confidence", "reasoning_summary"],
        }
    }

    def __init__(self, client: GemmaClient | None = None) -> None:
        """Initialize the agent.

        Args:
            client: GemmaClient instance. Pass None only for mock agents or
                    unit tests that don't invoke LLM methods. Any call to
                    call_tool(), run_verified_task(), or think() with
                    client=None will raise RuntimeError immediately.

        Example:
            >>> agent = VisionAgent(GemmaClient())
            >>> agent = MockAuditAgent(None)  # IS_MOCK = True, no LLM needed
        """
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.agent_name = self.__class__.__name__
        # agents/base_agent.py → .parent = agents/ → .parent = project root
        self.prompts_dir: Path = Path(__file__).parent.parent.resolve() / "prompts"
        self.logger.debug(
            "Initialized %s (mock=%s, client=%s)",
            self.agent_name,
            self.IS_MOCK,
            client is not None,
        )

    # ------------------------------------------------------------------
    # Abstract interface — every agent must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, **kwargs: Any) -> AgentResult:
        """Execute the agent's pipeline step.

        Must be implemented by every subclass. Should return _format_success()
        on success or _format_error() on any caught exception. Never raise
        from run() directly — wrap exceptions into AgentResult.error instead
        so PassportPipeline can decide whether to abort or continue.

        Returns:
            AgentResult with success=True and populated data dict on success,
            or success=False and error message on failure.
        Raises:
            NotImplementedError: If called directly on BaseAgent (abstract).
        """
        ...

    # ------------------------------------------------------------------
    # LLM delegation methods
    # ------------------------------------------------------------------

    def call_tool(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Single-phase structured output via native Ollama function calling.

        Delegates directly to GemmaClient.call_tool(). Use for agents where
        the data source is already deterministic (Vision, LCA+CSV, GS1).
        Retry logic and JSON fallback are handled inside GemmaClient — do NOT
        wrap this in additional retry loops.

        Args:
            prompt:        User-facing task description for the model.
            tools:         Tool definitions in OpenAI function calling format.
                           Must include EVIDENCE_SCHEMA for regulatory agents.
            system_prompt: Optional system role message. Load from prompts/
                           via _load_prompt(), never hardcode inline strings.

        Returns:
            dict: Parsed arguments from the first tool call.

        Raises:
            RuntimeError:          If self.client is None (mock agent).
            GemmaConnectionError:  If Ollama server is unreachable.
            GemmaResponseError:    If response cannot be parsed after retries.
        """
        if self.client is None:
            raise RuntimeError(
                f"[{self.agent_name}] call_tool() requires a GemmaClient instance. "
                f"This agent was initialized with client=None."
            )
        return self.client.call_tool(prompt, tools, system_prompt)

    def run_verified_task(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Two-phase anti-hallucination protocol: think → call_tool.

        Use for agents that handle regulatory facts where a hallucination is
        worse than no answer: RegulatoryConsultant (ESPR dates), LegalAgent
        (REACH SVHC flags). Do NOT use for VisionAgent, LCASpecialist, or
        GS1Specialist — the double call doubles CPU time for no benefit.

        Phase 1 — think():
            Model reasons about the prompt in extended thinking mode
            (think=True, no tools). Surfaces contradictions, cites regulation
            knowledge before committing to structured output.

        Phase 2 — call_tool():
            The thinking output is injected back into the prompt as
            [INTERNAL REASONING] context. Model structures ONLY what it
            already reasoned about. If Phase 1 says "2027" and Phase 2
            says "2025" — the contradiction is visible in DEBUG logs.

        Why think= and tools= cannot be combined in one call:
            Gemma 4 E4B does not support think=True and tools=[] simultaneously
            in a single Ollama chat() call. run_verified_task() solves this by
            making two separate calls. This is the intended contract, not a bug.

        Args:
            prompt:        Task description. Should include product context and
                           the specific regulation to evaluate.
            tools:         Tool definitions. Must include EVIDENCE_SCHEMA for
                           the output to be audit-traceable.
            system_prompt: Optional system role context. Load from prompts/.

        Returns:
            dict: Parsed tool call arguments from Phase 2.

        Raises:
            RuntimeError:         If self.client is None (mock agent).
            GemmaConnectionError: If Ollama server is unreachable.
            GemmaResponseError:   If Phase 2 response cannot be parsed.
        """
        if self.client is None:
            raise RuntimeError(
                f"[{self.agent_name}] run_verified_task() requires a GemmaClient instance. "
                f"This agent was initialized with client=None."
            )

        self.logger.info("[%s] Phase 1 — reasoning (think)...", self.agent_name)
        thinking: str = self.client.think(prompt)
        thinking = thinking.strip()
        if not thinking:
            raise RuntimeError(
                f"[{self.agent_name}] run_verified_task() Phase 1: think() returned empty "
                f"reasoning output. Cannot proceed to Phase 2."
            )
        self.logger.debug(
            "[%s] Phase 1 thinking output (first 300 chars): %s",
            self.agent_name,
            thinking[:300],
        )

        # Inject Phase 1 reasoning into Phase 2 prompt.
        # Standard \n separators are used intentionally — avoids markdown
        # rendering artefacts that can confuse tool call parsing.
        verified_prompt: str = (
            f"{prompt}\n\n"
            f"### INTERNAL REASONING:\n{thinking}\n\n"
            f"### INSTRUCTION:\n"
            f"Based on the reasoning above, call the tool with the structured data."
        )

        self.logger.info("[%s] Phase 2 — structuring (call_tool)...", self.agent_name)
        return self.client.call_tool(verified_prompt, tools, system_prompt)

    def think(self, prompt: str) -> str:
        """Delegate to GemmaClient.think() — extended reasoning mode.

        Available for agents that need raw thinking output before structuring
        it themselves. Prefer run_verified_task() for the full two-phase
        protocol. Use think() directly only when Phase 2 logic is custom.

        Args:
            prompt: The input prompt for extended reasoning.

        Returns:
            str: The model's reasoning text (unstructured).

        Raises:
            RuntimeError:         If self.client is None.
            GemmaConnectionError: If Ollama server is unreachable.
        """
        if self.client is None:
            raise RuntimeError(
                f"[{self.agent_name}] think() requires a GemmaClient instance."
            )
        return self.client.think(prompt)

    def _with_evidence_schema(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Inject EVIDENCE_SCHEMA into a single tool definition's parameters.

        Use before passing tools to run_verified_task() for RegulatoryConsultant
        and LegalAgent. Ensures evidence fields are always present in structured
        output without requiring each agent to manually merge the schema.

        Args:
            tool: A single tool definition dict in OpenAI function calling format.

        Returns:
            Deep copy of the tool with evidence injected into parameters.properties
            and "evidence" appended to parameters.required if not already present.
        """
        import copy
        tool_copy = copy.deepcopy(tool)
        parameters = tool_copy["function"]["parameters"]
        properties = parameters.setdefault("properties", {})
        properties.update(self.EVIDENCE_SCHEMA)
        required: list[str] = parameters.setdefault("required", [])
        if "evidence" not in required:
            required.append("evidence")
        return tool_copy

    def _with_evidence_schema_many(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Inject EVIDENCE_SCHEMA into all tools in a list.

        Convenience wrapper over _with_evidence_schema() for agents that
        define multiple tools.

        Args:
            tools: List of tool definition dicts.

        Returns:
            New list with evidence schema injected into each tool.
        """
        return [self._with_evidence_schema(tool) for tool in tools]

    # ------------------------------------------------------------------
    # Prompt loading
    # ------------------------------------------------------------------

    def _load_prompt(self, prompt_name: str) -> str:
        """Load prompt text from prompts/{name}.txt.

        Strips the .txt extension if included. All prompts must live under
        the project-root prompts/ directory — never inline prompt strings
        in agent .py files.

        Args:
            prompt_name: Filename without path, e.g. "vision_analysis" or
                         "vision_analysis.txt" (both accepted).

        Returns:
            str: Prompt content, whitespace-stripped.

        Raises:
            ValueError:        If prompt_name contains path traversal sequences.
            FileNotFoundError: If the prompt file does not exist at the resolved path.
            OSError:           If the file exists but cannot be read (permissions, encoding).
        """
        clean_name = Path(prompt_name).name.removesuffix(".txt")
        path: Path = (self.prompts_dir / f"{clean_name}.txt").resolve()

        if path.parent != self.prompts_dir.resolve():
            raise ValueError(
                f"[{self.agent_name}] Invalid prompt name '{prompt_name}': "
                f"path traversal is not allowed."
            )

        if not path.exists():
            self.logger.error(
                "[%s] Required prompt file missing: %s", self.agent_name, path
            )
            raise FileNotFoundError(
                f"Agent '{self.agent_name}' requires prompt file '{path}'. "
                f"Create it or check that prompts_dir is correct: {self.prompts_dir}"
            )

        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            self.logger.error(
                "[%s] Failed to read prompt file %s: %s", self.agent_name, path, exc
            )
            raise

    # ------------------------------------------------------------------
    # AgentResult constructors
    # ------------------------------------------------------------------

    def _format_success(self, data: dict[str, Any]) -> AgentResult:
        """Wrap successful agent output into a typed AgentResult envelope.

        Args:
            data: Agent-specific payload dict. Should not be empty on success;
                  a warning is logged if it is (helps catch silent failures).

        Returns:
            AgentResult with success=True and is_mock from class IS_MOCK flag.
        """
        if not data:
            self.logger.warning(
                "[%s] _format_success() called with empty data dict — possible silent failure.",
                self.agent_name,
            )
        result: AgentSuccessResult = {
            "success": True,
            "data": data,
            "agent": self.agent_name,
            "is_mock": self.IS_MOCK,
        }
        return result

    def _format_error(self, error: str | Exception) -> AgentResult:
        """Wrap agent failure into a typed AgentResult envelope.

        Accepts either a plain string message or an Exception instance.
        When an Exception is passed, exc_info=True is forwarded to the logger
        so the full traceback appears in log output without re-raising.

        Args:
            error: Error message string, or caught Exception instance.
                   Prefer passing the Exception directly to preserve traceback.

        Returns:
            AgentResult with success=False and error message.

        Example:
            except GemmaResponseError as exc:
                return self._format_error(exc)   # traceback preserved in logs
            except Exception as exc:
                return self._format_error(exc)
        """
        is_exc = isinstance(error, Exception)
        msg: str = str(error)
        self.logger.error(
            "[%s] Agent failure: %s",
            self.agent_name,
            msg,
            exc_info=is_exc,
        )
        result: AgentErrorResult = {
            "success": False,
            "error": msg,
            "agent": self.agent_name,
            "is_mock": self.IS_MOCK,
        }
        return result