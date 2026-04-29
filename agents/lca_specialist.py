from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class LCASpecialist(BaseAgent):
    """Sustainability evidence reviewer for PassportAI.

    LCASpecialist owns environmental evidence review and supplier-facing
    sustainability questions. It does not calculate or invent footprint,
    recycled-content, water, packaging, or material-composition values.
    """

    IS_MOCK = False

    SUPPORTED_GROUPS = {"textiles", "batteries", "electrical_appliances"}
    PROMPT_NAME = "lca_evidence_review"

    # Contract for the optional Gemma wording layer. The deterministic review
    # remains authoritative; Gemma can only phrase the explanation.
    FEEDBACK_TOOL = {
        "type": "function",
        "function": {
            "name": "write_sustainability_feedback",
            "description": "Write SME-facing feedback for an existing deterministic sustainability evidence review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_summary": {"type": "string"},
                    "business_risks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "severity": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                },
                                "why_it_matters": {"type": "string"},
                            },
                            "required": ["title", "severity", "why_it_matters"],
                            "additionalProperties": False,
                        },
                    },
                    "recommended_next_actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "priority": {
                                    "type": "string",
                                    "enum": ["now", "soon", "later"],
                                },
                                "action": {"type": "string"},
                                "owner": {
                                    "type": "string",
                                    "enum": [
                                        "manufacturer",
                                        "importer",
                                        "brand_owner",
                                        "supplier",
                                        "internal_compliance",
                                        "unknown",
                                    ],
                                },
                            },
                            "required": ["priority", "action", "owner"],
                            "additionalProperties": False,
                        },
                    },
                    "supplier_requests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "request": {"type": "string"},
                                "why_needed": {"type": "string"},
                                "document_type": {"type": "string"},
                            },
                            "required": ["request", "why_needed", "document_type"],
                            "additionalProperties": False,
                        },
                    },
                    "where_to_get_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "missing_topic": {"type": "string"},
                                "source": {"type": "string"},
                                "how_to_obtain": {"type": "string"},
                            },
                            "required": ["missing_topic", "source", "how_to_obtain"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "agent_summary",
                    "business_risks",
                    "recommended_next_actions",
                    "supplier_requests",
                    "where_to_get_data",
                ],
                "additionalProperties": False,
            },
        },
    }

    def run(
        self,
        product_group: str = "textiles",
        sustainability_evidence: dict[str, Any] | None = None,
        use_gemma_feedback: bool | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Review sustainability/LCA evidence for a product group.

        Args:
            product_group: One of textiles, batteries, electrical_appliances.
            sustainability_evidence: Optional structured references supplied by a
                user or supplier. Values are treated as references/evidence only;
                numeric environmental values are not generated.
            use_gemma_feedback: If True and a client is available, use Gemma to
                rewrite advisory wording. Deterministic facts are preserved.
        """
        try:
            normalized_group = self._normalize_product_group(product_group)
            evidence = sustainability_evidence or {}
            requirements = self._requirements_for(normalized_group)

            missing_fields = self._missing_fields_from_requirements(requirements, evidence)
            warnings = self._warnings_for(normalized_group, evidence)
            advisory = self._deterministic_advisory(normalized_group, missing_fields)

            if use_gemma_feedback is None:
                use_gemma_feedback = self.client is not None

            if use_gemma_feedback and self.client is not None:
                advisory = self._apply_gemma_feedback(
                    product_group=normalized_group,
                    missing_fields=missing_fields,
                    deterministic_advisory=advisory,
                )

            payload: AgentPayload = {
                "domain_data": {
                    "espr_core": {},
                    "voluntary_esg": self._voluntary_esg_projection(evidence),
                    "sectoral": {
                        "textiles": None,
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                },
                "assessment": {
                    "confidence_source": "supplier_documentation" if evidence else "insufficient_data",
                    "confidence_score": 0.8 if evidence else None,
                    "missing_fields": missing_fields,
                    "warnings": warnings,
                    "assumptions": self._assumptions_for(normalized_group, evidence),
                    "contradictions": [],
                    "needs_human_review": bool(missing_fields),
                },
                "advisory": advisory,
            }
            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _normalize_product_group(self, product_group: str) -> str:
        normalized = (product_group or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "battery": "batteries",
            "battery_pack": "batteries",
            "industrial_battery": "batteries",
            "electrical": "electrical_appliances",
            "electronics": "electrical_appliances",
            "electrical_appliance": "electrical_appliances",
            "textile": "textiles",
            "clothing": "textiles",
            "garment": "textiles",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in self.SUPPORTED_GROUPS:
            raise ValueError(f"Unsupported product_group: {product_group}")
        return normalized

    def _requirements_for(self, product_group: str) -> list[dict[str, str]]:
        if product_group == "batteries":
            return [
                {
                    "evidence_key": "carbon_footprint_reference",
                    "field": "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint",
                    "severity": "required",
                    "reason": "No supplier-backed battery carbon-footprint declaration is available.",
                    "action": "Request the battery carbon-footprint declaration and supporting methodology or verification references.",
                    "regulatory_basis": "REG_2023_1542_BATTERIES",
                    "where": "battery manufacturer sustainability dossier or verified product carbon-footprint declaration",
                    "why": "Battery carbon footprint is a high-sensitivity passport field and should not be estimated without source-backed evidence.",
                },
                {
                    "evidence_key": "critical_raw_materials_reference",
                    "field": "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials",
                    "severity": "required",
                    "reason": "No declared critical raw materials evidence is available.",
                    "action": "Request critical raw material composition and source-country evidence from the battery manufacturer.",
                    "regulatory_basis": "REG_2023_1542_BATTERIES",
                    "where": "battery technical file, supplier material declaration, or manufacturer sustainability dossier",
                    "why": "Critical raw materials data must be supported by supplier or manufacturer evidence.",
                },
                {
                    "evidence_key": "recycled_content_reference",
                    "field": "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent",
                    "severity": "required",
                    "reason": "No supplier-backed recycled-content evidence is available for the battery materials.",
                    "action": "Request recycled-content declarations and supporting evidence from the battery manufacturer.",
                    "regulatory_basis": "REG_2023_1542_BATTERIES",
                    "where": "supplier recycled-content declaration, certificate, or material declaration",
                    "why": "Recycled-content claims require document-backed evidence before publication.",
                },
                {
                    "evidence_key": "packaging_reference",
                    "field": "dpp.voluntaryEsg.packaging.material",
                    "severity": "optional",
                    "reason": "Packaging sustainability data is missing.",
                    "action": "Request packaging material and recyclability information from the supplier or packager.",
                    "regulatory_basis": None,
                    "where": "packaging specification or supplier packaging declaration",
                    "why": "Packaging data supports circularity reporting but should remain optional unless required by the selected profile.",
                },
            ]

        if product_group == "electrical_appliances":
            return [
                {
                    "evidence_key": "carbon_footprint_reference",
                    "field": "dpp.voluntaryEsg.footprint.carbonFootprint.gwpKgCo2e",
                    "severity": "recommended",
                    "reason": "No product-specific carbon-footprint evidence is available for the appliance.",
                    "action": "Request an environmental declaration, BOM-backed footprint information, or equivalent sustainability documentation.",
                    "regulatory_basis": None,
                    "where": "product environmental declaration, supplier sustainability dossier, or BOM-backed footprint study",
                    "why": "Appliance environmental claims should be supported by product-specific documentation.",
                },
                {
                    "evidence_key": "material_composition_reference",
                    "field": "dpp.sectoralElectricalAppliance.materialsAndSubstances.materialCompositionSummary",
                    "severity": "recommended",
                    "reason": "No material composition summary is available from BOM or supplier documentation.",
                    "action": "Request component or material breakdown for the appliance.",
                    "regulatory_basis": None,
                    "where": "bill of materials, supplier material declaration, or technical file",
                    "why": "Material composition supports repairability, recyclability, and substance-related review.",
                },
                {
                    "evidence_key": "recycled_content_reference",
                    "field": "dpp.voluntaryEsg.recycledContent.overallPercentage",
                    "severity": "optional",
                    "reason": "No declared recycled-content evidence is available for the appliance.",
                    "action": "Request recycled-content declarations or BOM-backed material information.",
                    "regulatory_basis": None,
                    "where": "supplier recycled-content declaration or BOM-backed material evidence",
                    "why": "Recycled-content claims should not be published without supporting evidence.",
                },
                {
                    "evidence_key": "packaging_reference",
                    "field": "dpp.voluntaryEsg.packaging.material",
                    "severity": "optional",
                    "reason": "Packaging sustainability data is missing.",
                    "action": "Request packaging material, recyclability, and recycled-content information.",
                    "regulatory_basis": None,
                    "where": "packaging specification or supplier packaging declaration",
                    "why": "Packaging data supports circularity reporting.",
                },
            ]

        return [
            {
                "evidence_key": "carbon_footprint_reference",
                "field": "dpp.voluntaryEsg.footprint.carbonFootprint.gwpKgCo2e",
                "severity": "recommended",
                "reason": "No declared or supplier-backed carbon-footprint data is available for the textile product.",
                "action": "Request supplier footprint data or a product-level environmental declaration before making sustainability claims.",
                "regulatory_basis": None,
                "where": "supplier environmental declaration, EPD, or product footprint documentation",
                "why": "Textile footprint claims should not be made without product-backed evidence.",
            },
            {
                "evidence_key": "recycled_content_reference",
                "field": "dpp.voluntaryEsg.recycledContent.overallPercentage",
                "severity": "recommended",
                "reason": "No declared recycled-content evidence is available.",
                "action": "Request a recycled-content declaration or supporting certificate from the supplier.",
                "regulatory_basis": None,
                "where": "supplier recycled-content declaration or certificate",
                "why": "Recycled-content claims require supplier-backed evidence.",
            },
            {
                "evidence_key": "water_consumption_reference",
                "field": "dpp.voluntaryEsg.footprint.waterConsumption.litersPerUnit",
                "severity": "optional",
                "reason": "No product-specific water-consumption data is available.",
                "action": "Request environmental declaration or process-water disclosure from the supplier if this metric is important for reporting.",
                "regulatory_basis": None,
                "where": "supplier environmental declaration or process-water disclosure",
                "why": "Water-consumption values should be evidence-backed if included.",
            },
            {
                "evidence_key": "packaging_reference",
                "field": "dpp.voluntaryEsg.packaging.material",
                "severity": "optional",
                "reason": "Packaging sustainability data is missing.",
                "action": "Request packaging material, recyclability, and recycled-content details.",
                "regulatory_basis": None,
                "where": "packaging specification or supplier packaging declaration",
                "why": "Packaging data supports circularity reporting.",
            },
        ]

    def _missing_fields_from_requirements(
        self,
        requirements: list[dict[str, Any]],
        evidence: dict[str, Any],
    ) -> list[dict[str, Any]]:
        missing_fields: list[dict[str, Any]] = []
        for requirement in requirements:
            if self._has_evidence(evidence, requirement["evidence_key"]):
                continue
            field = requirement["field"]
            missing_fields.append(
                {
                    "gap_id": f"{field}:missing",
                    "field": field,
                    "severity": requirement["severity"],
                    "blocking": requirement["severity"] in {"critical", "required"},
                    "reason_code": "missing",
                    "reason": requirement["reason"],
                    "why_it_matters": requirement["why"],
                    "action": requirement["action"],
                    "regulatory_basis": requirement["regulatory_basis"],
                    "deadline": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": True,
                    "source_domain": "lca",
                    "source_agents": ["LCASpecialist"],
                    "current_evidence_status": "absent",
                    "acceptable_evidence": ["document", "supplier_confirmation", "system_export"],
                    "where_to_get_data": requirement["where"],
                    "closure_condition": "Attach a supplier-backed or system-exported evidence reference. Do not estimate this value.",
                    "owner_hint": "supplier",
                }
            )
        return missing_fields

    def _has_evidence(self, evidence: dict[str, Any], key: str) -> bool:
        value = evidence.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            # A dict is acceptable only when it contains a reference-like field.
            return any(
                bool(str(value.get(ref_key, "")).strip())
                for ref_key in ("reference", "document_reference", "url", "document_url", "source")
            )
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    def _warnings_for(self, product_group: str, evidence: dict[str, Any]) -> list[str]:
        warnings = [
            "Environmental values must not be published as fact until supplier-backed evidence is provided.",
        ]
        unsupported_values = []
        for key in (
            "carbon_footprint_value",
            "gwp_kg_co2e",
            "recycled_content_percentage",
            "water_consumption_liters",
        ):
            if key in evidence and not self._has_matching_reference(evidence, key):
                unsupported_values.append(key)
        if unsupported_values:
            warnings.append(
                "Numeric sustainability values were supplied without matching evidence references and must remain untrusted: "
                + ", ".join(sorted(unsupported_values))
            )
        if product_group == "batteries":
            warnings.append(
                "Battery sustainability fields are high-sensitivity passport data and should use manufacturer-backed declarations."
            )
        return warnings

    def _has_matching_reference(self, evidence: dict[str, Any], value_key: str) -> bool:
        if value_key in {"carbon_footprint_value", "gwp_kg_co2e"}:
            return self._has_evidence(evidence, "carbon_footprint_reference")
        if value_key == "recycled_content_percentage":
            return self._has_evidence(evidence, "recycled_content_reference")
        if value_key == "water_consumption_liters":
            return self._has_evidence(evidence, "water_consumption_reference")
        return False

    def _assumptions_for(self, product_group: str, evidence: dict[str, Any]) -> list[str]:
        if evidence:
            return [
                "Only provided evidence references were treated as support. Missing references were not inferred.",
            ]
        return [
            f"No supplier-backed sustainability evidence was provided for product group '{product_group}'.",
        ]

    def _voluntary_esg_projection(self, evidence: dict[str, Any]) -> dict[str, Any] | None:
        if not evidence:
            return None
        # Pass through evidence references only. Do not create environmental values.
        allowed_keys = {
            "carbon_footprint_reference",
            "critical_raw_materials_reference",
            "recycled_content_reference",
            "water_consumption_reference",
            "material_composition_reference",
            "packaging_reference",
            "supply_chain_transparency_reference",
        }
        references = {
            key: deepcopy(value)
            for key, value in evidence.items()
            if key in allowed_keys and self._has_evidence(evidence, key)
        }
        if not references:
            return None
        return {"evidenceReferences": references}

    def _deterministic_advisory(
        self,
        product_group: str,
        missing_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if missing_fields:
            missing_topics = [item["field"].split(".")[-1] for item in missing_fields[:3]]
            summary = (
                f"Sustainability evidence for {product_group} is incomplete. "
                f"Missing topics include: {', '.join(missing_topics)}. "
                "The passport should not publish environmental claims until source-backed evidence is attached."
            )
        else:
            summary = (
                f"Sustainability evidence references for {product_group} are present for the configured review fields. "
                "Values should still be reviewed by a human before publication."
            )

        return {
            "agent_summary": summary,
            "business_risks": [
                {
                    "title": "Unsupported sustainability claims",
                    "severity": "high" if any(g["severity"] == "required" for g in missing_fields) else "medium",
                    "why_it_matters": "Environmental and circularity claims can undermine trust if they are not backed by supplier or system evidence.",
                }
            ],
            "recommended_next_actions": [
                {
                    "priority": "now" if missing_fields else "soon",
                    "action": "Request supplier-backed sustainability evidence references and attach them before publishing environmental claims.",
                    "owner": "supplier",
                }
            ],
            "supplier_requests": [
                {
                    "request": "Provide product-specific sustainability evidence references for the missing environmental fields.",
                    "why_needed": "Needed to keep environmental passport claims defensible and source-backed.",
                    "document_type": "supplier_sustainability_dossier",
                }
            ],
            "where_to_get_data": [
                {
                    "missing_topic": "Sustainability evidence",
                    "source": "supplier sustainability dossier / EPD / BOM / material declaration / packaging specification",
                    "how_to_obtain": "Request product-specific documents tied to the product model or SKU from the supplier or manufacturer.",
                }
            ],
            "next_batch_improvements": [
                "Collect sustainability evidence references during supplier onboarding instead of after passport generation starts.",
            ],
        }

    def _apply_gemma_feedback(
        self,
        *,
        product_group: str,
        missing_fields: list[dict[str, Any]],
        deterministic_advisory: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = self._load_prompt(self.PROMPT_NAME)
        task = (
            f"Product group: {product_group}\n"
            f"Deterministic missing sustainability fields:\n{json.dumps(missing_fields, ensure_ascii=False, indent=2)}\n\n"
            "Rewrite the advisory for a small business user. Preserve the deterministic facts."
        )
        try:
            result = self.call_tool(task, [self.FEEDBACK_TOOL], system_prompt=prompt)
        except Exception as exc:
            fallback = deepcopy(deterministic_advisory)
            fallback.setdefault("next_batch_improvements", []).append(
                f"Gemma sustainability feedback was unavailable; deterministic LCA review was preserved. Error: {exc}"
            )
            return fallback

        return self._sanitize_gemma_feedback(result, deterministic_advisory)

    def _sanitize_gemma_feedback(
        self,
        result: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            return fallback

        sanitized = deepcopy(fallback)
        summary = result.get("agent_summary")
        if isinstance(summary, str) and summary.strip():
            sanitized["agent_summary"] = summary.strip()

        for key in (
            "business_risks",
            "recommended_next_actions",
            "supplier_requests",
            "where_to_get_data",
        ):
            value = result.get(key)
            if isinstance(value, list) and value:
                sanitized[key] = self._clean_list_of_dicts(value)

        # Preserve deterministic next-batch improvements, because the model is
        # allowed to improve wording but not redefine process policy.
        sanitized["next_batch_improvements"] = fallback.get("next_batch_improvements", [])
        return sanitized

    def _clean_list_of_dicts(self, value: list[Any]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                cleaned.append({str(k): v for k, v in item.items() if isinstance(k, str)})
        return cleaned
