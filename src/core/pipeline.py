from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.storage.base import StorageProvider


@dataclass
class PipelineState:
    """Mutable shared state for one PassportPipeline run.

    This is the ONLY shared context passed between pipeline stages.
    Never store raw chain-of-thought or reasoning traces here.
    Store only structured intermediate outputs and stable agent envelopes.
    """

    passport_id: str
    image_path: Path
    description: str
    user_inputs: dict[str, Any] = field(default_factory=dict)

    # Routing / intake
    product_group_hint: str | None = None

    # Perception step
    standardized_image_path: Path | None = None
    image_description: str | None = None
    vision_result: dict[str, Any] | None = None

    # Generation / synthesis inputs
    regulatory_result: dict[str, Any] | None = None
    legal_result: dict[str, Any] | None = None
    lca_result: dict[str, Any] | None = None
    gs1_result: dict[str, Any] | None = None
    reconciled_domain_data: dict[str, Any] | None = None

    # Review step
    audit_result: dict[str, Any] | None = None
    readiness_score: int | None = None
    readiness_verdict: str | None = None
    is_publishable: bool | None = None
    gap_report_path: Path | None = None

    # Packaging / artifact step
    passport_json: dict[str, Any] | None = None
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
    reconciled_domain_data: dict[str, Any] | None
    passport_json: dict[str, Any] | None
    readiness_score: int | None
    readiness_verdict: str | None
    is_publishable: bool | None
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
    3. Reconcile boundary-clean agent outputs into one final domain snapshot
    4. Run DataAuditAgent on reconciled state
    5. Aggregate outputs into PipelineResult
    6. Keep orchestration OUTSIDE agents

    Expected agent keys in self.agents:
        - "vision"
        - "regulatory"
        - "legal"
        - "lca"
        - "gs1"
        - "audit"
        - "dpp_generator"   # optional in step 1.6
        - "gap_report"      # optional later
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
            self._run_gap_report_step(state)
            self._publish_artifact_package(state)
        except Exception as exc:
            state.errors.append(f"{type(exc).__name__}: {exc}")

        return self._build_result(state)

    def _run_perception_step(self, state: PipelineState) -> None:
        """Step 1: run vision and establish a routing hint.

        Important:
        - Vision owns visible evidence only.
        - product_group_hint is only a routing hint, not final classification truth.
        """
        vision_agent = self.agents.get("vision")
        if vision_agent is None:
            state.warnings.append(
                "Vision agent is not configured; proceeding without image perception."
            )
            return

        state.product_group_hint = self._user_inputs_product_group_hint(state)

        result = vision_agent.run(
            product_group_hint=state.product_group_hint,
            image_url=str(state.image_path),
            sufficient_visual_evidence=True,
        )
        state.vision_result = result
        state.agent_outputs["vision"] = result

        if not result.get("success", False):
            state.warnings.append("VisionAgent failed; continuing with user inputs only.")
            return

        payload = self._extract_payload_or_none(result)
        if payload is None:
            state.warnings.append("VisionAgent returned no usable payload.")
            return

        espr_core = payload.get("domain_data", {}).get("espr_core", {})
        state.image_description = espr_core.get("product_description")

        vision_hint = espr_core.get("product_group_hint")
        if isinstance(vision_hint, str) and vision_hint:
            state.product_group_hint = vision_hint

    def _run_generation_step(self, state: PipelineState) -> None:
        """Step 2: run domain agents and build reconciled_domain_data.

        This step does NOT generate passport_json.
        It produces the stable domain snapshot that later feeds:
        - DataAuditAgent now
        - DPPGenerator in step 1.6
        """
        product_group = self._select_product_group_for_domain_agents(state)

        regulatory_agent = self.agents.get("regulatory")
        legal_agent = self.agents.get("legal")
        lca_agent = self.agents.get("lca")
        gs1_agent = self.agents.get("gs1")

        if regulatory_agent is None:
            raise RuntimeError(
                "Regulatory agent is required to build reconciled domain data."
            )

        state.regulatory_result = regulatory_agent.run(product_group=product_group)
        state.agent_outputs["regulatory"] = state.regulatory_result

        if legal_agent is not None:
            state.legal_result = legal_agent.run(product_group=product_group)
            state.agent_outputs["legal"] = state.legal_result

        if lca_agent is not None:
            state.lca_result = lca_agent.run(product_group=product_group)
            state.agent_outputs["lca"] = state.lca_result

        if gs1_agent is not None:
            state.gs1_result = gs1_agent.run(
                product_group=product_group,
                persistent_identifier_value=state.user_inputs.get(
                    "persistent_identifier_value"
                ),
                operator_identifier_value=state.user_inputs.get(
                    "operator_identifier_value"
                ),
                facility_identifier_value=state.user_inputs.get(
                    "facility_identifier_value"
                ),
                public_resolver_url=state.user_inputs.get("public_resolver_url"),
            )
            state.agent_outputs["gs1"] = state.gs1_result

        state.reconciled_domain_data = self._build_reconciled_domain_data(state)

    def _run_review_step(self, state: PipelineState) -> None:
        """Step 3: run DataAuditAgent on reconciled domain data."""
        audit_agent = self.agents.get("audit")
        if audit_agent is None:
            raise RuntimeError("DataAuditAgent is required for review step.")

        if not isinstance(state.reconciled_domain_data, dict):
            raise RuntimeError("reconciled_domain_data is missing before review step.")

        state.audit_result = audit_agent.run(
            reconciled_domain_data=state.reconciled_domain_data,
            vision_result=state.vision_result,
            regulatory_result=state.regulatory_result,
            legal_result=state.legal_result,
            lca_result=state.lca_result,
            gs1_result=state.gs1_result,
        )
        state.agent_outputs["audit"] = state.audit_result

        audit_payload = self._require_success_payload(
            state.audit_result,
            "DataAuditAgent",
        )
        assessment = audit_payload.get("assessment", {})

        state.readiness_score = assessment.get("readiness_score")
        state.readiness_verdict = assessment.get("readiness_verdict")
        state.is_publishable = assessment.get("is_publishable")

    def _run_packaging_step(self, state: PipelineState) -> None:
        """Step 4: project reconciled state into a DPP JSON artifact.

        Invariants:
        - DPPGenerator consumes only reconciled_domain_data plus audit policy.
        - DPPGenerator does not see raw agent outputs.
        - passport_json is stored only after generator validation succeeds.
        - artifact_paths["passport.json"] points at the deterministic JSON artifact.
        """
        dpp_generator = self.agents.get("dpp_generator")
        if dpp_generator is None:
            state.warnings.append(
                "DPPGenerator is not configured yet; pipeline completed with audit-ready state only."
            )
            return

        if not isinstance(state.reconciled_domain_data, dict):
            raise RuntimeError("reconciled_domain_data is missing before packaging step.")

        audit_payload = self._require_success_payload(
            state.audit_result,
            "DataAuditAgent",
        )
        passport_public_url = self.storage.get_public_url(
            state.passport_id,
            "passport.json",
        )

        passport_json = dpp_generator.generate_from_reconciled_state(
            reconciled_domain_data=state.reconciled_domain_data,
            audit_payload=audit_payload,
            passport_id=state.passport_id,
            public_package_url=passport_public_url,
            qr_url=state.qr_url,
        )

        is_valid, validation_errors = dpp_generator.validate(passport_json)
        if not is_valid:
            rendered_errors = "; ".join(validation_errors) or "unknown validation error"
            raise RuntimeError(f"DPPGenerator validation failed: {rendered_errors}")

        artifact_path = self._write_passport_json_artifact(
            passport_id=state.passport_id,
            passport_json=passport_json,
        )

        state.passport_json = passport_json
        state.artifact_paths["passport.json"] = artifact_path
    
    def _run_gap_report_step(self, state: PipelineState) -> None:
        """Step 5: render a human-readable remediation report from audit output.

        Invariants:
        - GapReportGenerator consumes DataAuditAgent output only.
        - It must not read passport_json or raw agent outputs.
        - The report is an artifact projection, not a second auditor.
        """
        gap_report_generator = self.agents.get("gap_report")
        if gap_report_generator is None:
            return

        if state.audit_result is None:
            raise RuntimeError("audit_result is missing before gap report step.")

        report_path = gap_report_generator.generate(
            audit_result=state.audit_result,
            output_dir=self._get_package_dir(state.passport_id),
            passport_id=state.passport_id,
        )

        state.gap_report_path = report_path
        state.artifact_paths["gap_report.html"] = report_path


    def _publish_artifact_package(self, state: PipelineState) -> None:
        """Save the package once all configured artifact renderers have succeeded."""
        if not state.artifact_paths:
            return

        state.package_url = self.storage.save_package(
            state.passport_id,
            dict(state.artifact_paths),
        )

    def _build_reconciled_domain_data(self, state: PipelineState) -> dict[str, Any]:
        """Build one final domain snapshot from boundary-clean agent outputs.

        Merge policy:
        - RegulatoryConsultant provides the classification anchor.
        - Other agents only overlay the fields they own.
        - No agent may overwrite another agent's ownership boundary.
        """
        regulatory_payload = self._require_success_payload(
            state.regulatory_result,
            "RegulatoryConsultant",
        )
        reconciled = deepcopy(regulatory_payload["domain_data"])

        espr_core = reconciled.setdefault("espr_core", {})
        selected_group = espr_core.get("product_group")

        if not isinstance(selected_group, str) or not selected_group:
            raise ValueError(
                "RegulatoryConsultant did not provide espr_core.product_group"
            )

        vision_payload = self._extract_payload_or_none(state.vision_result)
        if vision_payload is not None:
            self._apply_vision_overlay(reconciled, vision_payload, selected_group)

        legal_payload = self._extract_payload_or_none(state.legal_result)
        if legal_payload is not None:
            self._apply_legal_overlay(reconciled, legal_payload, selected_group)

        lca_payload = self._extract_payload_or_none(state.lca_result)
        if lca_payload is not None:
            self._apply_lca_overlay(reconciled, lca_payload)

        gs1_payload = self._extract_payload_or_none(state.gs1_result)
        if gs1_payload is not None:
            self._apply_gs1_overlay(reconciled, gs1_payload)

        self._apply_user_input_overlay(reconciled, state.user_inputs, selected_group)

        return reconciled

    def _apply_vision_overlay(
        self,
        reconciled: dict[str, Any],
        payload: dict[str, Any],
        selected_group: str,
    ) -> None:
        source_espr = payload.get("domain_data", {}).get("espr_core", {})
        target_espr = reconciled.setdefault("espr_core", {})

        for key in (
            "product_name",
            "product_description",
            "brand_name",
            "model_name",
            "model_number",
            "serial_number",
            "batch_lot",
            "product_image_url",
            "visible_markings",
            "visible_certifications",
            "visible_warnings",
        ):
            if key in source_espr:
                target_espr[key] = source_espr.get(key)

        source_sector = (
            payload.get("domain_data", {}).get("sectoral", {}).get(selected_group)
        )
        if isinstance(source_sector, dict):
            target_sector = (
                reconciled.setdefault("sectoral", {}).setdefault(selected_group, {})
            )
            target_sector.update(source_sector)

    def _apply_legal_overlay(
        self,
        reconciled: dict[str, Any],
        payload: dict[str, Any],
        selected_group: str,
    ) -> None:
        source_espr = payload.get("domain_data", {}).get("espr_core", {})
        target_espr = reconciled.setdefault("espr_core", {})

        if "compliance_hint" in source_espr:
            target_espr["compliance_hint"] = source_espr.get("compliance_hint")

        source_sector = (
            payload.get("domain_data", {}).get("sectoral", {}).get(selected_group)
        )
        if isinstance(source_sector, dict):
            target_sector = (
                reconciled.setdefault("sectoral", {}).setdefault(selected_group, {})
            )
            for key, value in source_sector.items():
                target_sector[key] = value

    def _apply_lca_overlay(
        self,
        reconciled: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        if "voluntary_esg" in payload.get("domain_data", {}):
            reconciled["voluntary_esg"] = payload["domain_data"].get("voluntary_esg")

    def _apply_gs1_overlay(
        self,
        reconciled: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        source_espr = payload.get("domain_data", {}).get("espr_core", {})
        target_espr = reconciled.setdefault("espr_core", {})

        for key in ("identifiers_hint", "data_carrier_hint"):
            if key in source_espr:
                target_espr[key] = source_espr.get(key)

    def _apply_user_input_overlay(
        self,
        reconciled: dict[str, Any],
        user_inputs: dict[str, Any],
        selected_group: str,
    ) -> None:
        """Apply only non-classification user overrides.

        User input must not overwrite product_group / espr_category / sector_profile.
        """
        espr_core = reconciled.setdefault("espr_core", {})

        for key in (
            "product_name",
            "product_description",
            "brand_name",
            "model_name",
            "model_number",
            "serial_number",
            "batch_lot",
        ):
            if key in user_inputs:
                espr_core[key] = user_inputs[key]

        sectoral_patch = user_inputs.get("sectoral", {})
        if isinstance(sectoral_patch, dict):
            selected_patch = sectoral_patch.get(selected_group)
            if isinstance(selected_patch, dict):
                reconciled.setdefault("sectoral", {}).setdefault(
                    selected_group, {}
                ).update(selected_patch)

    def _get_package_dir(self, passport_id: str) -> Path:
        get_package_dir = getattr(self.storage, "get_package_dir", None)
        if callable(get_package_dir):
            return Path(get_package_dir(passport_id))
        return Path("output") / passport_id
    
    def _write_passport_json_artifact(
        self,
        *,
        passport_id: str,
        passport_json: dict[str, Any],
    ) -> Path:
        """Persist generated DPP JSON to a deterministic local path."""
        
        package_dir = self._get_package_dir(passport_id)
        package_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = package_dir / "passport.json"
        artifact_path.write_text(
            json.dumps(passport_json, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return artifact_path

    def _extract_payload_or_none(
        self,
        result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(result, dict):
            return None
        if {"domain_data", "assessment", "advisory"}.issubset(result.keys()):
            return result
        if result.get("success") is True and isinstance(result.get("data"), dict):
            return result["data"]
        return None

    def _require_success_payload(
        self,
        result: dict[str, Any] | None,
        agent_name: str,
    ) -> dict[str, Any]:
        payload = self._extract_payload_or_none(result)
        if payload is None:
            raise RuntimeError(f"{agent_name} did not return a usable success payload.")
        return payload

    def _user_inputs_product_group_hint(self, state: PipelineState) -> str | None:
        value = state.user_inputs.get("product_group")
        return value if isinstance(value, str) and value else None

    def _select_product_group_for_domain_agents(self, state: PipelineState) -> str:
        """Choose only a routing hint for domain agents.

        Ownership note:
        - This is not final classification truth.
        - RegulatoryConsultant still owns final classification in reconciled_domain_data.
        """
        explicit = state.user_inputs.get("product_group")
        if isinstance(explicit, str) and explicit:
            return explicit

        if isinstance(state.product_group_hint, str) and state.product_group_hint:
            return state.product_group_hint

        return "textiles"

    def _build_result(self, state: PipelineState) -> PipelineResult:
        return PipelineResult(
            success=len(state.errors) == 0,
            passport_id=state.passport_id,
            reconciled_domain_data=state.reconciled_domain_data,
            passport_json=state.passport_json,
            readiness_score=state.readiness_score,
            readiness_verdict=state.readiness_verdict,
            is_publishable=state.is_publishable,
            package_url=state.package_url,
            qr_url=state.qr_url,
            warnings=list(state.warnings),
            errors=list(state.errors),
            artifact_paths=dict(state.artifact_paths),
            agent_outputs=dict(state.agent_outputs),
        )