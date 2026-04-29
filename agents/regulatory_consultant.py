from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class RegulatoryConsultant(BaseAgent):
    """Deterministic regulatory classification plus optional Gemma explanation.

    Ownership boundary:
    - owns product-group classification, sector profile selection, regulatory
      requiredness hints, and SME-facing explanation of classification uncertainty.
    - does not own legal proof, supplier-confirmed values, identifiers, or final
      publishability.

    Gemma may be used only as a wording/explanation layer. The deterministic
    payload remains the source of structured regulatory facts.
    """

    IS_MOCK = False

    SUPPORTED_PRODUCT_GROUPS = {
        "textiles",
        "batteries",
        "electrical_appliances",
    }

    PRODUCT_GROUP_ALIASES = {
        "textile": "textiles",
        "textiles": "textiles",
        "clothing": "textiles",
        "garment": "textiles",
        "apparel": "textiles",
        "battery": "batteries",
        "batteries": "batteries",
        "industrial_battery": "batteries",
        "battery_pack": "batteries",
        "electrical": "electrical_appliances",
        "electronics": "electrical_appliances",
        "electrical_appliance": "electrical_appliances",
        "electrical_appliances": "electrical_appliances",
        "appliance": "electrical_appliances",
        "appliances": "electrical_appliances",
    }

    def __init__(
        self,
        client: Any | None = None,
        *,
        use_gemma_explanation: bool = False,
    ) -> None:
        super().__init__(client=client)
        self.use_gemma_explanation = use_gemma_explanation

    def run(
        self,
        product_group: str = "textiles",
        *,
        product_description: str | None = None,
        vision_result: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
        use_gemma_explanation: bool | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Classify product group and return a regulatory perspective payload.

        The core classification is deterministic. Optional Gemma explanation can
        enrich `advisory.gemma_explanation`, but cannot change domain_data,
        assessment.missing_fields, readiness, or any product truth.
        """
        try:
            normalized_group = self._normalize_product_group(product_group)
            if normalized_group == "textiles":
                payload = self._build_textiles_payload()
            elif normalized_group == "batteries":
                payload = self._build_batteries_payload()
            elif normalized_group == "electrical_appliances":
                payload = self._build_electrical_payload()
            else:
                raise ValueError(f"Unsupported product_group: {product_group}")

            payload["assessment"]["classification"] = {
                "input_product_group": product_group,
                "normalized_product_group": normalized_group,
                "method": "deterministic_supported_category_mapping",
                "gemma_used_for_classification": False,
            }

            should_explain = (
                self.use_gemma_explanation
                if use_gemma_explanation is None
                else use_gemma_explanation
            )
            if should_explain and self.client is not None:
                payload = self._attach_gemma_explanation(
                    payload=payload,
                    product_description=product_description,
                    vision_result=vision_result,
                    user_context=user_context,
                )

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _normalize_product_group(self, product_group: str | None) -> str:
        raw = (product_group or "").strip().lower().replace("-", "_").replace(" ", "_")
        return self.PRODUCT_GROUP_ALIASES.get(raw, raw)

    def _attach_gemma_explanation(
        self,
        *,
        payload: AgentPayload,
        product_description: str | None,
        vision_result: dict[str, Any] | None,
        user_context: dict[str, Any] | None,
    ) -> AgentPayload:
        enhanced = deepcopy(payload)
        try:
            prompt_template = self._load_prompt("regulatory_classification")
            prompt = self._build_explanation_prompt(
                prompt_template=prompt_template,
                payload=payload,
                product_description=product_description,
                vision_result=vision_result,
                user_context=user_context,
            )
            raw = self.client.generate(prompt, temperature=0.1)  # type: ignore[union-attr]
            explanation = self._parse_gemma_explanation(raw)
            enhanced["advisory"]["gemma_explanation"] = explanation
            enhanced["assessment"].setdefault("warnings", []).append(
                "RegulatoryConsultant: Gemma explanation was used for wording only; deterministic classification remained unchanged."
            )
        except Exception as exc:
            enhanced["assessment"].setdefault("warnings", []).append(
                "RegulatoryConsultant: Gemma explanation failed; deterministic regulatory payload was preserved."
            )
            enhanced["advisory"]["gemma_explanation"] = self._fallback_explanation(
                enhanced, error=str(exc)
            )
        return enhanced

    def _build_explanation_prompt(
        self,
        *,
        prompt_template: str,
        payload: AgentPayload,
        product_description: str | None,
        vision_result: dict[str, Any] | None,
        user_context: dict[str, Any] | None,
    ) -> str:
        context = {
            "product_description": product_description,
            "vision_result": vision_result or {},
            "user_context": user_context or {},
            "deterministic_regulatory_payload": {
                "domain_data": payload["domain_data"],
                "assessment": {
                    "confidence_source": payload["assessment"].get("confidence_source"),
                    "confidence_score": payload["assessment"].get("confidence_score"),
                    "missing_fields": payload["assessment"].get("missing_fields", []),
                    "warnings": payload["assessment"].get("warnings", []),
                    "needs_human_review": payload["assessment"].get("needs_human_review"),
                },
                "advisory": {
                    "agent_summary": payload["advisory"].get("agent_summary"),
                    "recommended_next_actions": payload["advisory"].get("recommended_next_actions", []),
                    "where_to_get_data": payload["advisory"].get("where_to_get_data", []),
                },
            },
        }
        return (
            f"{prompt_template.strip()}\n\n"
            "### DETERMINISTIC CONTEXT JSON\n"
            f"{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n\n"
            "Return JSON only."
        )

    def _parse_gemma_explanation(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemma regulatory explanation must be a JSON object")

        user_explanation = self._bounded_string(
            parsed.get("user_explanation"),
            fallback="Regulatory classification was completed using deterministic supported-category rules.",
            max_len=900,
        )
        classification_uncertainty = self._bounded_string(
            parsed.get("classification_uncertainty"),
            fallback="Human review remains required where supplier evidence is missing.",
            max_len=600,
        )
        required_evidence_hints = self._bounded_string_list(
            parsed.get("required_evidence_hints"),
            max_items=8,
            max_len=240,
        )
        next_questions = self._bounded_string_list(
            parsed.get("next_questions"),
            max_items=6,
            max_len=240,
        )

        return {
            "user_explanation": user_explanation,
            "classification_uncertainty": classification_uncertainty,
            "required_evidence_hints": required_evidence_hints,
            "next_questions": next_questions,
            "source": "gemma_wording_only",
        }

    def _fallback_explanation(self, payload: AgentPayload, *, error: str) -> dict[str, Any]:
        espr_core = payload["domain_data"].get("espr_core", {})
        product_group = espr_core.get("product_group", "unknown")
        missing_fields = payload["assessment"].get("missing_fields", [])
        hints = [
            item.get("action", "Provide supplier-backed evidence.")
            for item in missing_fields[:5]
            if isinstance(item, dict)
        ]
        return {
            "user_explanation": (
                f"This product is classified as {product_group}. The regulatory classification is deterministic; "
                "Gemma explanation was not used because the explanation layer failed."
            ),
            "classification_uncertainty": "Human review remains required until missing evidence is provided.",
            "required_evidence_hints": hints,
            "next_questions": [],
            "source": "deterministic_fallback",
            "error": error[:300],
        }

    def _bounded_string(self, value: Any, *, fallback: str, max_len: int) -> str:
        if not isinstance(value, str) or not value.strip():
            return fallback
        return value.strip()[:max_len]

    def _bounded_string_list(
        self,
        value: Any,
        *,
        max_items: int,
        max_len: int,
    ) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip()[:max_len])
            if len(out) >= max_items:
                break
        return out

    def _base_assessment(
        self,
        *,
        confidence_score: float,
        missing_fields: list[dict[str, Any]],
        warnings: list[str],
        assumptions: list[str],
    ) -> dict[str, Any]:
        return {
            "confidence_source": "regulation_text",
            "confidence_score": confidence_score,
            "missing_fields": missing_fields,
            "warnings": warnings,
            "assumptions": assumptions,
            "contradictions": [],
            "needs_human_review": True,
        }

    def _base_domain_data(
        self,
        *,
        product_group: str,
        sector_profile_name: str,
        regulatory_source: list[str],
        legal_basis: list[str],
        sectoral_payload: dict[str, Any],
    ) -> dict[str, Any]:
        sectoral = {
            "textiles": None,
            "batteries": None,
            "electrical_appliances": None,
        }
        sectoral[product_group] = sectoral_payload
        return {
            "espr_core": {
                "product_group": product_group,
                "sector_profile": {
                    "name": sector_profile_name,
                    "version": "1.0.0",
                    "regulatory_source": regulatory_source,
                },
                "espr_category": product_group,
                "granularity_level": "model",
                "legal_basis": legal_basis,
                "cn_code": None,
            },
            "sectoral": sectoral,
        }

    def _build_textiles_payload(self) -> AgentPayload:
        missing_fields = [
            {
                "field": "dpp.regulatedCore.productIdentity.cnCode",
                "severity": "required",
                "reason": "CN code is needed to support classification and customs-facing product identification.",
                "action": "Confirm the CN code with the manufacturer, importer, or customs/compliance documentation.",
                "regulatory_basis": "ESPR_2024_1781",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralTextile.composition.materialComposition",
                "severity": "required",
                "reason": "Textile composition is a core sector-specific data requirement.",
                "action": "Request a composition sheet or bill of materials showing component/material percentages.",
                "regulatory_basis": "ESPR_2024_1781",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralTextile.careAndUse.careSymbols",
                "severity": "recommended",
                "reason": "Care symbols improve usability and passport completeness for textile products.",
                "action": "Collect care label information from the physical label or supplier technical sheet.",
                "regulatory_basis": "SECTORAL_ACT_PENDING",
                "can_be_inferred": False,
                "requires_supplier_confirmation": False,
                "source_domain": "regulatory",
            },
        ]
        return {
            "domain_data": self._base_domain_data(
                product_group="textiles",
                sector_profile_name="textile_core_v1",
                regulatory_source=["REG_2024_1781_ESPR", "SECTORAL_ACT_PENDING"],
                legal_basis=["ESPR_2024_1781"],
                sectoral_payload={
                    "substances_of_concern_present": None,
                    "country_of_manufacture": None,
                    "country_of_origin": None,
                    "year_of_manufacture": None,
                    "durability_years": None,
                    "durability_basis": None,
                    "repairability_applicable": True,
                    "repair_service_available": None,
                    "reusable": None,
                    "recyclable": None,
                    "take_back_available": None,
                    "disassembly_required": None,
                },
            ),
            "assessment": self._base_assessment(
                confidence_score=0.93,
                missing_fields=missing_fields,
                warnings=["Textile sector requirements may evolve as sectoral delegated acts mature."],
                assumptions=["Product is treated as a textile article for regulatory profiling."],
            ),
            "advisory": {
                "agent_summary": "Classified as textiles under the textile_core_v1 regulatory profile. Main blockers are missing CN code and material composition evidence.",
                "business_risks": [
                    {
                        "title": "Incomplete textile identity data",
                        "severity": "high",
                        "why_it_matters": "Composition and classification data are needed before a textile passport can be defended.",
                    }
                ],
                "recommended_next_actions": [
                    {"priority": "now", "action": "Request a textile composition sheet with component percentages.", "owner": "supplier"},
                    {"priority": "now", "action": "Confirm the CN code with compliance documentation.", "owner": "internal_compliance"},
                ],
                "supplier_requests": [
                    {"request": "Provide material composition by component and percentage.", "why_needed": "Needed for textile sector composition requirements.", "document_type": "composition_sheet"},
                    {"request": "Provide manufacturing country and care label data.", "why_needed": "Needed for textile manufacturing and care fields.", "document_type": "technical_specification"},
                ],
                "where_to_get_data": [
                    {"missing_topic": "CN code", "source": "customs documentation / importer compliance file", "how_to_obtain": "Check customs classification documents or ask the importer/compliance owner."}
                ],
                "next_batch_improvements": ["Require composition sheets and care label data from suppliers before onboarding a new textile SKU."],
            },
        }

    def _build_batteries_payload(self) -> AgentPayload:
        missing_fields = [
            {
                "field": "dpp.sectoralBattery.batteryClassification.batteryCategory",
                "severity": "critical",
                "reason": "Battery category is required to determine applicable passport obligations.",
                "action": "Confirm whether the battery is portable, industrial, EV, LMT, or SLI.",
                "regulatory_basis": "BATTERY_REG_2023_1542_ARTICLE_77",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralBattery.batteryClassification.chemistry",
                "severity": "required",
                "reason": "Battery chemistry is needed for battery classification and passport content.",
                "action": "Request the battery chemistry declaration from the manufacturer or technical datasheet.",
                "regulatory_basis": "BATTERY_REG_2023_1542",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint",
                "severity": "required",
                "reason": "Battery passport sustainability fields require source-backed declarations.",
                "action": "Request the battery carbon-footprint declaration and supporting methodology or verification references.",
                "regulatory_basis": "BATTERY_REG_2023_1542",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
        ]
        return {
            "domain_data": self._base_domain_data(
                product_group="batteries",
                sector_profile_name="battery_passport_annex_xiii_v1",
                regulatory_source=["REG_2023_1542_BATTERIES"],
                legal_basis=["BATTERY_REG_2023_1542"],
                sectoral_payload={
                    "battery_category": None,
                    "chemistry": None,
                    "is_rechargeable": None,
                    "passport_required": True,
                    "passport_requirement_basis": "ARTICLE_77_BATTERY_REGULATION",
                    "ce_marking_present": None,
                },
            ),
            "assessment": self._base_assessment(
                confidence_score=0.95,
                missing_fields=missing_fields,
                warnings=["Battery passport readiness depends on regulatory classification and source-backed technical evidence."],
                assumptions=["Product is treated as a battery subject to battery passport profiling until reviewed."],
            ),
            "advisory": {
                "agent_summary": "Classified as batteries under the battery_passport_annex_xiii_v1 profile. Main blockers are unresolved battery category, chemistry, and sustainability evidence.",
                "business_risks": [
                    {
                        "title": "Battery category or chemistry not confirmed",
                        "severity": "high",
                        "why_it_matters": "Incorrect classification can lead to the wrong passport structure and missing mandatory battery data.",
                    }
                ],
                "recommended_next_actions": [
                    {"priority": "now", "action": "Request official battery chemistry and category documentation.", "owner": "supplier"},
                    {"priority": "now", "action": "Confirm whether the product falls under Article 77 battery passport obligations.", "owner": "internal_compliance"},
                ],
                "supplier_requests": [
                    {"request": "Provide battery chemistry, category, and manufacturing date.", "why_needed": "Needed to establish battery passport classification.", "document_type": "technical_datasheet"},
                    {"request": "Provide carbon footprint declaration for the battery passport.", "why_needed": "Needed for battery sustainability and composition fields.", "document_type": "battery_passport_supporting_document"},
                ],
                "where_to_get_data": [
                    {"missing_topic": "Battery chemistry and category", "source": "manufacturer technical datasheet", "how_to_obtain": "Ask the battery manufacturer or authorized supplier for the declared chemistry and battery class."}
                ],
                "next_batch_improvements": ["Require battery chemistry, category, and passport-related sustainability documents before procurement approval."],
            },
        }

    def _build_electrical_payload(self) -> AgentPayload:
        missing_fields = [
            {
                "field": "dpp.sectoralElectricalAppliance.applianceClassification.applianceType",
                "severity": "critical",
                "reason": "Appliance type is needed to choose the correct sectoral interpretation and evidence set.",
                "action": "Confirm the appliance type from product technical documentation.",
                "regulatory_basis": "ESPR_2024_1781",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralElectricalAppliance.energyAndPerformance.energyEfficiency.energyClass",
                "severity": "required",
                "reason": "Energy class is a core field when energy-labelling obligations apply.",
                "action": "Request the official energy label or EPREL evidence.",
                "regulatory_basis": "ENERGY_LABELLING_2017_1369",
                "can_be_inferred": False,
                "requires_supplier_confirmation": True,
                "source_domain": "regulatory",
            },
            {
                "field": "dpp.sectoralElectricalAppliance.documentationAndSoftware.userManualUrl",
                "severity": "recommended",
                "reason": "User-facing documentation improves passport completeness and serviceability.",
                "action": "Collect the user manual URL or upload a manual asset.",
                "regulatory_basis": "SECTORAL_ACT_PENDING",
                "can_be_inferred": False,
                "requires_supplier_confirmation": False,
                "source_domain": "regulatory",
            },
        ]
        return {
            "domain_data": self._base_domain_data(
                product_group="electrical_appliances",
                sector_profile_name="electrical_appliance_espr_ready_v1",
                regulatory_source=["REG_2024_1781_ESPR", "REG_2017_1369_ENERGY_LABELLING", "SECTORAL_ACT_PENDING"],
                legal_basis=["ESPR_2024_1781", "ENERGY_LABELLING_2017_1369", "ROHS_RELEVANT_EEE_CHECK"],
                sectoral_payload={
                    "appliance_type": None,
                    "energy_related_product": None,
                    "energy_label_required": None,
                    "eprel_registered": None,
                    "repairability_applicable": True,
                    "service_information_available": None,
                    "contains_battery": None,
                },
            ),
            "assessment": self._base_assessment(
                confidence_score=0.91,
                missing_fields=missing_fields,
                warnings=["Electrical appliance requirements vary by final confirmed appliance class and energy-labelling scope."],
                assumptions=["Product is treated as an electrical appliance within the ESPR-ready profile."],
            ),
            "advisory": {
                "agent_summary": "Classified as electrical_appliances under the electrical_appliance_espr_ready_v1 profile. Main blockers are unresolved appliance type, energy-labelling scope, and missing documentation links.",
                "business_risks": [
                    {
                        "title": "Wrong appliance classification or energy-labelling scope",
                        "severity": "high",
                        "why_it_matters": "If appliance type or label scope is wrong, the passport may omit mandatory sector-specific fields.",
                    }
                ],
                "recommended_next_actions": [
                    {"priority": "now", "action": "Confirm the appliance type and whether energy-labelling obligations apply.", "owner": "internal_compliance"},
                    {"priority": "soon", "action": "Request official energy label or EPREL evidence from the supplier.", "owner": "supplier"},
                ],
                "supplier_requests": [
                    {"request": "Provide the appliance classification and product technical datasheet.", "why_needed": "Needed to confirm regulatory product type and expected passport fields.", "document_type": "technical_datasheet"},
                    {"request": "Provide the energy label / EPREL evidence and user manual.", "why_needed": "Needed for energy and documentation fields.", "document_type": "energy_label_or_manual"},
                ],
                "where_to_get_data": [
                    {"missing_topic": "Energy class and label status", "source": "supplier technical file / energy label evidence / EPREL registration evidence", "how_to_obtain": "Ask the manufacturer or importer for official label evidence and registration identifiers."}
                ],
                "next_batch_improvements": ["Require energy-label evidence, manuals, and appliance classification data before listing a new electrical product."],
            },
        }
