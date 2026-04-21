from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.storage.base import StorageProvider


@dataclass
class PipelineState:
    """Mutable shared state for one PassportPipeline run.

    This is the ONLY shared context passed between pipeline stages.
    Never store raw chain-of-thought or shared reasoning traces here.
    Store only structured intermediate outputs.
    """

    passport_id: str
    image_path: Path
    description: str
    user_inputs: dict[str, Any] = field(default_factory=dict)

    # Perception step
    standardized_image_path: Path | None = None
    image_description: str | None = None
    vision_result: dict[str, Any] | None = None

    # Generation step
    merged_product_data: dict[str, Any] = field(default_factory=dict)
    regulatory_result: dict[str, Any] | None = None
    legal_result: dict[str, Any] | None = None
    lca_result: dict[str, Any] | None = None
    passport_json: dict[str, Any] | None = None

    # Review step
    audit_result: dict[str, Any] | None = None
    readiness_score: int | None = None
    gap_report_path: Path | None = None

    # Packaging step
    gs1_result: dict[str, Any] | None = None
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    package_url: str | None = None
    qr_url: str | None = None

    # Diagnostics
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    agent_outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Final immutable output returned by PassportPipeline.run()."""

    success: bool
    passport_id: str
    passport_json: dict[str, Any] | None
    readiness_score: int | None
    package_url: str | None
    qr_url: str | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    agent_outputs: dict[str, Any] = field(default_factory=dict)


class PassportPipeline:
    """High-level orchestrator for PassportAI.

    Responsibilities:
    1. Create and maintain PipelineState
    2. Execute pipeline stages in the correct order
    3. Aggregate outputs into PipelineResult
    4. Keep orchestration OUTSIDE agents

    Expected agent keys in self.agents later:
        - "vision"
        - "regulatory"
        - "legal"
        - "lca"
        - "audit"
        - "gs1"
        - "dpp_generator"   # optional, if stored as an object in agents
    """

    def __init__(
        self,
        agents: dict[str, Any],
        storage: StorageProvider,
    ) -> None:
        self.agents = agents
        self.storage = storage

    def run(
        self,
        image_path: str | Path,
        description: str = "",
        user_inputs: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run the full DPP pipeline from input image to final packaged result.

        Current version is intentionally synchronous.
        Add concurrency only after real agents exist and step boundaries are stable.
        """
        state = PipelineState(
            passport_id=str(uuid4()),
            image_path=Path(image_path),
            description=description,
            user_inputs=user_inputs or {},
        )

        if not state.image_path.exists():
            state.errors.append(f"Image file not found: {state.image_path}")
            return self._build_result(state)

        try:
            self._run_perception_step(state)
            self._run_generation_step(state)
            self._run_review_step(state)
            self._run_packaging_step(state)
        except Exception as exc:
            state.errors.append(f"{type(exc).__name__}: {exc}")

        return self._build_result(state)

    def _run_perception_step(self, state: PipelineState) -> None:
        """Step 1: extract product facts from image and user input.

        Planned responsibilities:
        - standardize / preprocess photo
        - run VisionAgent
        - save raw perception outputs into state
        - prepare merged_product_data seed
        """
        # TODO: implement in step 1.5 / 2.0
        return None

    def _run_generation_step(self, state: PipelineState) -> None:
        """Step 2: produce structured passport draft inputs.

        Planned responsibilities:
        - merge user_inputs with vision_result
        - run RegulatoryConsultant
        - run LegalAgent
        - run LCASpecialist
        - generate passport_json via DPPGenerator
        """
        # TODO: implement after perception step is stable
        return None

    def _run_review_step(self, state: PipelineState) -> None:
        """Step 3: audit completeness and consistency.

        Planned responsibilities:
        - run DataAuditAgent
        - compute readiness_score
        - generate optional gap report path
        - append warnings/errors for missing required fields
        """
        # TODO: implement after passport_json structure is stable
        return None

    def _run_packaging_step(self, state: PipelineState) -> None:
        """Step 4: package outputs, upload/store, and generate QR.

        Planned responsibilities:
        - run GS1Specialist
        - render HTML / PDF artifacts
        - save package via storage provider
        - generate QR URL / QR image last
        """
        # TODO: implement after review step is stable
        return None

    def _build_result(self, state: PipelineState) -> PipelineResult:
        """Convert mutable PipelineState into final PipelineResult."""
        return PipelineResult(
            success=len(state.errors) == 0,
            passport_id=state.passport_id,
            passport_json=state.passport_json,
            readiness_score=state.readiness_score,
            package_url=state.package_url,
            qr_url=state.qr_url,
            warnings=list(state.warnings),
            errors=list(state.errors),
            artifact_paths=dict(state.artifact_paths),
            agent_outputs=dict(state.agent_outputs),
        )