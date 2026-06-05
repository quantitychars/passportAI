from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from .base_agent import BaseAgent
from .contracts import AgentPayload
from .vision_mock_payloads import (
    build_batteries_mock_payload,
    build_electrical_mock_payload,
    build_insufficient_data_payload,
    build_textiles_mock_payload,
)


class VisionAgent(BaseAgent):
    """
    VisionAgent owns:
    - OCR / label extraction
    - visible markings / certifications / warnings
    - product appearance hints
    - weak product-group hints
    - perception gaps
    - photo retake advice

    VisionAgent does NOT own:
    - final product classification
    - legal basis
    - sector profile
    - regulatory applicability
    - supplier-verified facts
    - LCA values
    - GS1 identifiers
    - legal/compliance truth

    Vision writes what is visible, not what is legally true.
    """

    IS_MOCK = True

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client=client)
        # client=None keeps deterministic fixture mode for tests.
        # client=GemmaClient(...) activates real Ollama/Gemma-backed vision.
        self.IS_MOCK = client is None

    def run(
        self,
        product_group_hint: str | None = "textiles",
        image_url: str | None = None,
        sufficient_visual_evidence: bool = True,
        description: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            if self.client is not None:
                payload = self._run_gemma_vision(
                    image_url=image_url,
                    description=description,
                    product_group_hint=product_group_hint,
                    sufficient_visual_evidence=sufficient_visual_evidence,
                )
            elif not sufficient_visual_evidence or product_group_hint is None:
                payload = build_insufficient_data_payload(image_url=image_url)
            elif product_group_hint == "textiles":
                payload = build_textiles_mock_payload(image_url=image_url)
            elif product_group_hint == "batteries":
                payload = build_batteries_mock_payload(image_url=image_url)
            elif product_group_hint == "electrical_appliances":
                payload = build_electrical_mock_payload(image_url=image_url)
            else:
                raise ValueError(f"Unsupported product_group_hint: {product_group_hint}")

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _run_gemma_vision(
        self,
        *,
        image_url: str | None,
        description: str,
        product_group_hint: str | None,
        sufficient_visual_evidence: bool,
    ) -> AgentPayload:
        if not sufficient_visual_evidence:
            return build_insufficient_data_payload(image_url=image_url)

        if not image_url:
            raise ValueError("image_url is required for Gemma-backed vision analysis")

        prompt = self._build_gemma_vision_prompt(
            description=description,
            product_group_hint=product_group_hint,
        )

        raw = self.client.analyze_image(Path(image_url), prompt)
        parsed = self._parse_model_json(raw)

        return self._build_payload_from_gemma_output(
            parsed,
            image_url=image_url,
            product_group_hint=product_group_hint,
        )

    def _build_gemma_vision_prompt(
        self,
        *,
        description: str,
        product_group_hint: str | None,
    ) -> str:
        base_prompt = self._load_prompt("vision_analysis")

        context = (
            f"User description: {description or 'not provided'}\n"
            f"Pipeline product group hint: {product_group_hint or 'not provided'}\n"
            "For this PassportAI vertical slice, normalize category to one of: "
            "textiles, batteries, electrical_appliances, unknown. "
            "If the product appears electronic, use electrical_appliances. "
            "Only report markings, certifications, and materials visible in the image "
            "or clearly inferable from the visible product type. Do not invent model, "
            "serial, supplier, or country facts. "
            "Return exactly one JSON object matching the provided schema. "
            "Use empty arrays when evidence is absent. "
            "Use null only for dimensions that cannot be estimated. "
            "Use 'unknown' when category is not supported. "
            "Do not include markdown, comments, explanations, or trailing prose."
        )

        return base_prompt.replace("[USER_DESCRIPTION]", context)

    def _parse_model_json(self, raw: str) -> dict[str, Any]:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Gemma vision response is empty")

        cleaned = re.sub(r"^```[^\n]*\n?", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            raise ValueError("Gemma vision response must be a JSON object")

        return parsed

    def _build_payload_from_gemma_output(
        self,
        data: dict[str, Any],
        *,
        image_url: str | None,
        product_group_hint: str | None,
    ) -> AgentPayload:
        product_group = self._normalize_product_group(data.get("category"))
        confidence = self._coerce_confidence(data.get("confidence"))

        if product_group is None:
            payload = build_insufficient_data_payload(image_url=image_url)
            payload["assessment"]["confidence_score"] = confidence
            payload["assessment"].setdefault("warnings", []).append(
                "Gemma vision did not identify a supported product group with enough confidence."
            )
            payload["assessment"].setdefault("assumptions", []).append(
                f"Raw Gemma category: {data.get('category')!r}."
            )
            return payload

        materials = self._clean_string_list(data.get("materials"))
        colors = self._clean_string_list(data.get("colors"))
        certifications = self._clean_string_list(data.get("certifications_visible"))
        markings = self._clean_string_list(data.get("special_markings"))
        product_type = self._clean_string(data.get("product_type"))

        description_parts = []
        if product_type:
            description_parts.append(product_type)
        if colors:
            description_parts.append("colors: " + ", ".join(colors))
        if materials:
            description_parts.append("visible/inferred materials: " + ", ".join(materials))

        product_description = (
            "; ".join(description_parts)
            if description_parts
            else "Gemma visual analysis did not identify specific product attributes."
        )

        sectoral = {
            "textiles": None,
            "batteries": None,
            "electrical_appliances": None,
        }

        if product_group == "textiles":
            sectoral["textiles"] = {
                "material_composition": self._build_visual_material_composition(materials),
                "care_symbols": [],
                "care_instructions_text": None,
                "substances_of_concern_present": None,
                "country_of_manufacture": None,
                "country_of_origin": None,
            }
        elif product_group == "batteries":
            sectoral["batteries"] = {
                "battery_model_identifier": None,
                "serial_number": None,
                "chemistry": self._guess_visible_battery_chemistry(materials + markings),
                "ce_marking_present": self._contains_case_insensitive(
                    markings + certifications,
                    "ce",
                ),
                "label_information": {"observed_text": markings},
                "safety_instructions_url": None,
            }
        elif product_group == "electrical_appliances":
            sectoral["electrical_appliances"] = {
                "appliance_type": product_type,
                "energy_class": None,
                "user_manual_url": None,
                "installation_manual_url": None,
                "contains_battery": None,
                "repair_instructions_url": None,
            }

        missing_fields = []
        if not markings and not certifications:
            missing_fields.append(
                {
                    "field": "image.visible_label.markings",
                    "severity": "recommended",
                    "reason": "No readable label markings or certifications were extracted from the image.",
                    "action": "Upload a close-up of product labels, tags, and packaging text.",
                    "regulatory_basis": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": False,
                    "source_domain": "vision",
                }
            )

        if product_group_hint and product_group_hint != product_group:
            warning = (
                f"Gemma visual category hint '{product_group}' differs from pipeline hint "
                f"'{product_group_hint}'. RegulatoryConsultant still owns final classification."
            )
        else:
            warning = (
                "Gemma visual output is treated as visible evidence only, not as final "
                "regulatory classification or supplier-verified truth."
            )

        return {
            "domain_data": {
                "espr_core": {
                    "product_name": product_type,
                    "product_description": product_description,
                    "brand_name": None,
                    "model_name": None,
                    "model_number": None,
                    "serial_number": None,
                    "batch_lot": None,
                    "product_image_url": image_url,
                    "visible_markings": markings,
                    "visible_certifications": certifications,
                    "visible_warnings": [],
                    "product_group_hint": product_group,
                },
                "sectoral": sectoral,
            },
            "assessment": {
                "confidence_source": "model_estimate",
                "confidence_score": confidence,
                "missing_fields": missing_fields,
                "warnings": [warning],
                "assumptions": [
                    "Product attributes come from Gemma image analysis and require human review before publication."
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": (
                    "Gemma extracted visible product attributes and weak category hints from the uploaded image. "
                    "Supplier-backed facts are still required for publication readiness."
                ),
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Review the Gemma-extracted visual attributes against the physical product and labels.",
                        "owner": "manufacturer",
                    },
                    {
                        "priority": "soon",
                        "action": "Upload close-up label photos if markings, model number, or origin are not readable.",
                        "owner": "supplier",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Supplier-verified product identity and label evidence",
                        "source": "product label, packaging, declaration documents, supplier data sheet",
                        "how_to_obtain": "Collect close-up photos and supplier documents; do not rely on the image-only inference as final truth.",
                    }
                ],
            },
        }

    def _normalize_product_group(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

        mapping = {
            "textile": "textiles",
            "textiles": "textiles",
            "battery": "batteries",
            "batteries": "batteries",
            "electronics": "electrical_appliances",
            "electronic": "electrical_appliances",
            "electrical": "electrical_appliances",
            "electrical_appliance": "electrical_appliances",
            "electrical_appliances": "electrical_appliances",
        }

        return mapping.get(normalized)

    def _coerce_confidence(self, value: Any) -> float | None:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None

        return max(0.0, min(1.0, confidence))

    def _clean_string(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        cleaned = value.strip()
        return cleaned or None

    def _clean_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        cleaned: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())

        return cleaned

    def _build_visual_material_composition(
        self,
        materials: list[str],
    ) -> list[dict[str, Any]]:
        if not materials:
            return []

        if len(materials) == 1:
            percentage = 100.0
        else:
            # Image analysis cannot prove exact fiber percentages. Use 0.0 to force
            # DPPGenerator to emit its explicit unknown-composition placeholder rather
            # than pretending the visual estimate is supplier-verified composition.
            percentage = 0.0

        return [
            {
                "component": "body",
                "material": material,
                "percentage": percentage,
                "bio_based": None,
            }
            for material in materials[:5]
        ]

    def _guess_visible_battery_chemistry(self, values: list[str]) -> str | None:
        joined = " ".join(values).lower()

        if "li-ion" in joined or "lithium" in joined:
            return "lithium_ion"
        if "lead" in joined:
            return "lead_acid"

        return None

    def _contains_case_insensitive(self, values: list[str], needle: str) -> bool:
        needle = needle.lower()
        return any(needle in value.lower() for value in values)
