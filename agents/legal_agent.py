from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class LegalAgent(BaseAgent):
    """Legal evidence reviewer for PassportAI.

    Ownership boundary:
    - owns legal evidence gaps, document/reference requiredness, claim
      substantiation warnings, access/disclosure guidance, and user-facing legal
      evidence feedback.
    - does not own final product classification, final compliance certification,
      supplier-verified facts, identifiers, LCA values, or publishability.

    The deterministic payload is the source of structured legal facts. Gemma may
    optionally add human-readable feedback, but it cannot change missing fields,
    document presence, or any product truth.
    """

    IS_MOCK = False

    PRODUCT_GROUP_ALIASES = {
        "textile": "textiles",
        "textiles": "textiles",
        "clothing": "textiles",
        "garment": "textiles",
        "apparel": "textiles",
        "battery": "batteries",
        "batteries": "batteries",
        "battery_pack": "batteries",
        "industrial_battery": "batteries",
        "electrical": "electrical_appliances",
        "electronics": "electrical_appliances",
        "electrical_appliance": "electrical_appliances",
        "electrical_appliances": "electrical_appliances",
        "appliance": "electrical_appliances",
        "appliances": "electrical_appliances",
    }

    LEGAL_FEEDBACK_TOOL = {
        "type": "function",
        "function": {
            "name": "explain_legal_evidence_review",
            "description": (
                "Explain an existing deterministic legal evidence review to a "
                "small business user without changing the legal review result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Plain-language summary of the deterministic legal evidence review.",
                    },
                    "why_it_matters": {
                        "type": "string",
                        "description": "Why the missing legal evidence matters before publication.",
                    },
                    "next_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Actionable legal evidence collection steps for the SME.",
                    },
                },
                "required": ["summary", "why_it_matters", "next_steps"],
                "additionalProperties": False,
            },
        },
    }

    def __init__(
        self,
        client: Any | None = None,
        *,
        use_gemma_feedback: bool = False,
    ) -> None:
        super().__init__(client=client)
        self.use_gemma_feedback = use_gemma_feedback

    def run(
        self,
        product_group: str = "textiles",
        *,
        evidence_refs: dict[str, Any] | None = None,
        visible_claims: list[str] | None = None,
        use_gemma_feedback: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Review legal evidence availability for the selected product group.

        `evidence_refs` and keyword arguments may provide document references or
        URLs. The agent treats evidence as present only when a non-empty reference
        or URL is provided. It never invents documents.
        """
        try:
            normalized_group = self._normalize_product_group(product_group)
            evidence = self._normalize_evidence_refs(evidence_refs, kwargs)
            visible_claims = self._clean_string_list(visible_claims)

            if normalized_group == "textiles":
                payload = self._build_textiles_payload(evidence, visible_claims)
            elif normalized_group == "batteries":
                payload = self._build_batteries_payload(evidence, visible_claims)
            elif normalized_group == "electrical_appliances":
                payload = self._build_electrical_payload(evidence, visible_claims)
            else:  # defensive; _normalize_product_group already validates
                raise ValueError(f"Unsupported product_group: {product_group}")

            should_use_gemma = (
                self.use_gemma_feedback
                if use_gemma_feedback is None
                else use_gemma_feedback
            )
            if should_use_gemma and self.client is not None:
                payload = deepcopy(payload)
                payload["advisory"]["legal_feedback"] = self._generate_gemma_feedback(
                    payload=payload,
                    product_group=normalized_group,
                )

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _build_textiles_payload(
        self,
        evidence: dict[str, str | None],
        visible_claims: list[str],
    ) -> AgentPayload:
        declaration_present = False
        technical_present = self._has_evidence(evidence, "technical_documentation")
        substances_present = self._has_evidence(evidence, "substances_declaration")
        certifications_present = self._has_evidence(evidence, "certification")
        has_visible_claims = bool(visible_claims)

        missing_fields = []
        if not technical_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.regulatedCore.compliance.technicalDocumentation",
                    severity="required",
                    reason="Technical documentation is not attached or referenced.",
                    action="Request a technical file reference or upload the supporting technical documentation.",
                    regulatory_basis="ESPR_2024_1781",
                    why_it_matters="A textile passport needs defensible technical documentation before regulated claims are published.",
                    where_to_get_data="supplier technical file or internal compliance document repository",
                    document_type="technical_documentation",
                )
            )
        if not substances_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.sectoralTextile.substances",
                    severity="required",
                    reason="No documentary statement is available for substances of concern or chemical compliance.",
                    action="Request a chemical declaration or REACH/SVHC statement from the supplier.",
                    regulatory_basis="ESPR_2024_1781",
                    why_it_matters="Chemical and substances declarations are evidence fields, not visual claims.",
                    where_to_get_data="supplier chemical declaration, REACH statement, or compliance pack",
                    document_type="chemical_declaration",
                )
            )
        if has_visible_claims and not certifications_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.sectoralTextile.certificationAndClaims.certifications",
                    severity="recommended",
                    reason="Visible or user-provided certification claims are not backed by certificate documents.",
                    action="Request certificate PDF, certificate number, issuer, scope, and validity dates before publishing the claim.",
                    regulatory_basis="SECTORAL_ACT_PENDING",
                    why_it_matters="Unsupported certification claims weaken passport trust and may create claim-risk.",
                    where_to_get_data="supplier compliance pack or certificate issuer documentation",
                    document_type="certificate_pdf",
                )
            )

        return self._payload(
            product_group="textiles",
            declaration_required=False,
            declaration_present=declaration_present,
            declaration_reference=None,
            declaration_url=None,
            technical_present=technical_present,
            technical_reference=evidence.get("technical_documentation_reference"),
            technical_url=evidence.get("technical_documentation_url"),
            sectoral={
                "textiles": {
                    "substances_declaration_reference": evidence.get("substances_declaration_reference"),
                    "certification_references": self._evidence_list(evidence, "certification"),
                },
                "batteries": None,
                "electrical_appliances": None,
            },
            missing_fields=missing_fields,
            warnings=[
                "Textile legal review checks document availability. It does not certify claims from visual evidence alone."
            ],
            assumptions=[
                "Textile conformity assessment is treated as evidence-based and document-backed."
            ],
            summary=(
                "Textile legal evidence review is incomplete. Technical documentation "
                "and substances evidence should be attached before publication."
            ),
        )

    def _build_batteries_payload(
        self,
        evidence: dict[str, str | None],
        visible_claims: list[str],
    ) -> AgentPayload:
        declaration_present = self._has_evidence(evidence, "declaration_of_conformity")
        technical_present = self._has_evidence(evidence, "technical_documentation")
        battery_declaration_present = self._has_evidence(evidence, "battery_declaration_of_conformity")

        missing_fields = []
        if not declaration_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.regulatedCore.compliance.declarationOfConformity",
                    severity="critical",
                    reason="Declaration of Conformity is required but not attached or referenced.",
                    action="Request the Declaration of Conformity from the manufacturer or importer before publication.",
                    regulatory_basis="REG_2023_1542_BATTERIES",
                    why_it_matters="The passport must not imply battery conformity without document-backed evidence.",
                    where_to_get_data="manufacturer compliance file or importer documentation pack",
                    document_type="declaration_of_conformity",
                )
            )
        if not technical_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.regulatedCore.compliance.technicalDocumentation",
                    severity="required",
                    reason="Battery technical documentation is not attached or referenced.",
                    action="Request the battery technical documentation reference or upload the relevant file.",
                    regulatory_basis="REG_2023_1542_BATTERIES",
                    why_it_matters="Technical documentation supports the regulated claims projected into the passport.",
                    where_to_get_data="manufacturer technical file or importer compliance pack",
                    document_type="technical_documentation",
                )
            )
        if not battery_declaration_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.sectoralBattery.conformityAndInformation.declarationOfConformityReference",
                    severity="required",
                    reason="The sector-specific battery conformity reference is missing.",
                    action="Attach the declaration reference used to substantiate battery conformity information.",
                    regulatory_basis="REG_2023_1542_BATTERIES",
                    why_it_matters="Battery passport conformity fields need an explicit document reference.",
                    where_to_get_data="battery manufacturer declaration or importer compliance file",
                    document_type="battery_declaration_reference",
                )
            )

        return self._payload(
            product_group="batteries",
            declaration_required=True,
            declaration_present=declaration_present,
            declaration_reference=evidence.get("declaration_of_conformity_reference"),
            declaration_url=evidence.get("declaration_of_conformity_url"),
            technical_present=technical_present,
            technical_reference=evidence.get("technical_documentation_reference"),
            technical_url=evidence.get("technical_documentation_url"),
            sectoral={
                "textiles": None,
                "batteries": {
                    "declaration_of_conformity_reference": evidence.get("battery_declaration_of_conformity_reference"),
                    "technical_documentation_reference": evidence.get("technical_documentation_reference"),
                },
                "electrical_appliances": None,
            },
            missing_fields=missing_fields,
            warnings=[
                "Battery products should not be published with conformity implications unless declaration and technical references are available."
            ],
            assumptions=[
                "Battery legal review is based on document availability, not visual markings alone."
            ],
            summary=(
                "Battery legal evidence review checks declaration and technical "
                "documentation references required before passport publication."
            ),
        )

    def _build_electrical_payload(
        self,
        evidence: dict[str, str | None],
        visible_claims: list[str],
    ) -> AgentPayload:
        declaration_present = self._has_evidence(evidence, "declaration_of_conformity")
        technical_present = self._has_evidence(evidence, "technical_documentation")
        rohs_present = self._has_evidence(evidence, "rohs_declaration")

        missing_fields = []
        if not declaration_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.regulatedCore.compliance.declarationOfConformity",
                    severity="critical",
                    reason="Declaration of Conformity is expected but not attached or referenced.",
                    action="Request the Declaration of Conformity covering applicable electrical appliance requirements.",
                    regulatory_basis="ESPR_2024_1781;ROHS_DIRECTIVE_2011_65_EU",
                    why_it_matters="Electrical appliances should not publish conformity-facing passport claims without supporting declarations.",
                    where_to_get_data="manufacturer or importer declaration pack",
                    document_type="declaration_of_conformity",
                )
            )
        if not technical_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.regulatedCore.compliance.technicalDocumentation",
                    severity="required",
                    reason="Technical documentation is not attached or referenced.",
                    action="Request appliance technical documentation or a stable technical file reference.",
                    regulatory_basis="ESPR_2024_1781",
                    why_it_matters="Technical documentation supports safety, performance, repairability, and conformity-related claims.",
                    where_to_get_data="manufacturer technical file or importer compliance repository",
                    document_type="technical_documentation",
                )
            )
        if not rohs_present:
            missing_fields.append(
                self._missing_field(
                    field="dpp.sectoralElectricalAppliance.compliance.rohsDeclarationReference",
                    severity="required",
                    reason="RoHS evidence is not attached or referenced for the electrical appliance.",
                    action="Request RoHS declaration or restricted-substance compliance evidence from the manufacturer.",
                    regulatory_basis="ROHS_DIRECTIVE_2011_65_EU",
                    why_it_matters="Restricted-substance evidence should be document-backed, not inferred from product appearance.",
                    where_to_get_data="manufacturer RoHS declaration or supplier restricted-substance statement",
                    document_type="rohs_declaration",
                )
            )

        return self._payload(
            product_group="electrical_appliances",
            declaration_required=True,
            declaration_present=declaration_present,
            declaration_reference=evidence.get("declaration_of_conformity_reference"),
            declaration_url=evidence.get("declaration_of_conformity_url"),
            technical_present=technical_present,
            technical_reference=evidence.get("technical_documentation_reference"),
            technical_url=evidence.get("technical_documentation_url"),
            sectoral={
                "textiles": None,
                "batteries": None,
                "electrical_appliances": {
                    "technical_documentation_reference": evidence.get("technical_documentation_reference"),
                    "rohs_declaration_reference": evidence.get("rohs_declaration_reference"),
                },
            },
            missing_fields=missing_fields,
            warnings=[
                "Electrical appliance legal review checks evidence references; it does not certify compliance."
            ],
            assumptions=[
                "RoHS and conformity evidence are treated as document-backed fields."
            ],
            summary=(
                "Electrical appliance legal evidence review checks conformity, "
                "technical documentation, and RoHS evidence references."
            ),
        )

    def _payload(
        self,
        *,
        product_group: str,
        declaration_required: bool,
        declaration_present: bool,
        declaration_reference: str | None,
        declaration_url: str | None,
        technical_present: bool,
        technical_reference: str | None,
        technical_url: str | None,
        sectoral: dict[str, Any],
        missing_fields: list[dict[str, Any]],
        warnings: list[str],
        assumptions: list[str],
        summary: str,
    ) -> AgentPayload:
        needs_human_review = bool(missing_fields)
        return {
            "domain_data": {
                "espr_core": {
                    "compliance_hint": {
                        "declaration_of_conformity": {
                            "required": declaration_required,
                            "present": declaration_present,
                            "document_url": declaration_url,
                            "document_reference": declaration_reference,
                        },
                        "technical_documentation": {
                            "present": technical_present,
                            "document_reference": technical_reference,
                            "document_url": technical_url,
                            "storage_location": "internal",
                            "last_updated": None,
                        },
                        "access_control": self._access_control_for(product_group),
                        "claim_review": {
                            "unsupported_claims": [],
                            "document_backed_claims": [],
                            "needs_claim_substantiation": needs_human_review,
                        },
                    }
                },
                "sectoral": sectoral,
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.9 if not needs_human_review else 0.86,
                "missing_fields": missing_fields,
                "warnings": warnings,
                "assumptions": assumptions,
                "contradictions": [],
                "needs_human_review": needs_human_review,
            },
            "advisory": {
                "agent_summary": summary,
                "business_risks": self._business_risks(missing_fields),
                "recommended_next_actions": self._recommended_actions(missing_fields),
                "supplier_requests": self._supplier_requests(missing_fields),
                "where_to_get_data": self._where_to_get_data(missing_fields),
                "next_batch_improvements": [
                    "Collect legal evidence references during supplier onboarding before passport publication."
                ],
            },
        }

    def _generate_gemma_feedback(
        self,
        *,
        payload: AgentPayload,
        product_group: str,
    ) -> dict[str, Any]:
        prompt_template = self._load_prompt("legal_evidence_review")
        prompt = prompt_template.replace("[PRODUCT_GROUP]", product_group).replace(
            "[LEGAL_REVIEW_JSON]",
            json.dumps(
                {
                    "agent_summary": payload["advisory"].get("agent_summary"),
                    "missing_fields": payload["assessment"].get("missing_fields", []),
                    "warnings": payload["assessment"].get("warnings", []),
                    "needs_human_review": payload["assessment"].get("needs_human_review"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

        try:
            raw = self.call_tool(prompt, [self.LEGAL_FEEDBACK_TOOL])
        except Exception as exc:
            return {
                "source": "deterministic_fallback",
                "summary": "Legal feedback explanation could not be generated; deterministic legal review was preserved.",
                "why_it_matters": str(exc),
                "next_steps": [
                    "Use the deterministic missing evidence list to request legal documents from the supplier or manufacturer."
                ],
            }

        return self._sanitize_gemma_feedback(raw)

    def _sanitize_gemma_feedback(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Gemma legal feedback must be a dict")

        next_steps = self._clean_string_list(raw.get("next_steps"))[:5]
        return {
            "source": "gemma_wording",
            "summary": self._clean_string(raw.get("summary"))
            or "Legal evidence review requires follow-up.",
            "why_it_matters": self._clean_string(raw.get("why_it_matters"))
            or "Missing legal evidence weakens the defensibility of the passport.",
            "next_steps": next_steps
            or ["Request missing legal evidence from the supplier or manufacturer."],
        }

    def _missing_field(
        self,
        *,
        field: str,
        severity: str,
        reason: str,
        action: str,
        regulatory_basis: str,
        why_it_matters: str,
        where_to_get_data: str,
        document_type: str,
    ) -> dict[str, Any]:
        return {
            "field": field,
            "severity": severity,
            "reason": reason,
            "action": action,
            "regulatory_basis": regulatory_basis,
            "can_be_inferred": False,
            "requires_supplier_confirmation": True,
            "source_domain": "legal",
            "source_agents": ["LegalAgent"],
            "reason_code": "document_absent",
            "current_evidence_status": "absent",
            "acceptable_evidence": ["document", "supplier_confirmation"],
            "why_it_matters": why_it_matters,
            "owner_hint": "supplier",
            "where_to_get_data": where_to_get_data,
            "closure_condition": f"Attach or reference a valid {document_type.replace('_', ' ')}.",
        }

    def _business_risks(self, missing_fields: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not missing_fields:
            return []
        return [
            {
                "title": "Unsupported legal evidence",
                "severity": "high" if any(item.get("severity") == "critical" for item in missing_fields) else "medium",
                "why_it_matters": "Publishing a passport with missing legal evidence can create unsupported compliance claims.",
            }
        ]

    def _recommended_actions(self, missing_fields: list[dict[str, Any]]) -> list[dict[str, str]]:
        actions = []
        for item in missing_fields[:5]:
            actions.append(
                {
                    "priority": "now" if item.get("severity") in {"critical", "required"} else "soon",
                    "action": self._clean_string(item.get("action"))
                    or "Request missing legal evidence.",
                    "owner": "supplier",
                }
            )
        return actions

    def _supplier_requests(self, missing_fields: list[dict[str, Any]]) -> list[dict[str, str]]:
        requests = []
        for item in missing_fields:
            requests.append(
                {
                    "request": f"Provide authoritative evidence for {item['field']}.",
                    "why_needed": self._clean_string(item.get("why_it_matters"))
                    or "Needed to close a legal evidence gap.",
                    "document_type": self._document_type_for_field(item["field"]),
                }
            )
        return requests

    def _where_to_get_data(self, missing_fields: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "missing_topic": item["field"],
                "source": self._clean_string(item.get("where_to_get_data"))
                or "supplier or manufacturer documentation pack",
                "how_to_obtain": self._clean_string(item.get("action"))
                or "Request the missing document from the supplier.",
            }
            for item in missing_fields
        ]

    def _access_control_for(self, product_group: str) -> dict[str, Any]:
        public_sections = ["productIdentity", "dataCarrier", "passportIdentity"]
        restricted_sections = {
            "marketSurveillanceAuthorities": [
                "compliance",
                "technicalDocumentation",
                "auditTrail",
            ],
            "customs": ["productIdentity", "identifiers", "economicOperators"],
            "economicOperators": ["supplierDeclarations", "qualityAssessment"],
        }
        confidential = ["supplier commercial terms"]
        if product_group == "batteries":
            restricted_sections["marketSurveillanceAuthorities"].append(
                "batteryTechnicalFile"
            )
        return {
            "public_sections": public_sections,
            "restricted_sections": restricted_sections,
            "confidential_business_information": confidential,
        }

    def _document_type_for_field(self, field: str) -> str:
        if "declarationOfConformity" in field:
            return "declaration_of_conformity"
        if "technicalDocumentation" in field:
            return "technical_documentation"
        if "rohs" in field.lower():
            return "rohs_declaration"
        if "substances" in field:
            return "chemical_declaration"
        if "certification" in field:
            return "certificate_pdf"
        return "supporting_legal_evidence"

    def _normalize_product_group(self, value: Any) -> str:
        clean = self._clean_string(value).lower()
        normalized = self.PRODUCT_GROUP_ALIASES.get(clean)
        if normalized is None:
            raise ValueError(
                "Unsupported product_group for LegalAgent: "
                f"{value!r}. Expected textiles, batteries, or electrical_appliances."
            )
        return normalized

    def _normalize_evidence_refs(
        self,
        evidence_refs: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> dict[str, str | None]:
        raw: dict[str, Any] = {}
        if isinstance(evidence_refs, dict):
            raw.update(evidence_refs)
        raw.update(kwargs)

        normalized: dict[str, str | None] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            normalized[key] = self._clean_string(value) or None
        return normalized

    def _has_evidence(self, evidence: dict[str, str | None], stem: str) -> bool:
        candidates = (
            f"{stem}_reference",
            f"{stem}_url",
            f"{stem}_document_reference",
            f"{stem}_document_url",
        )
        return any(bool(evidence.get(key)) for key in candidates)

    def _evidence_list(self, evidence: dict[str, str | None], stem: str) -> list[str]:
        values = []
        for key in (f"{stem}_reference", f"{stem}_url"):
            value = evidence.get(key)
            if value:
                values.append(value)
        return values

    def _clean_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _clean_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = []
        for item in value:
            text = self._clean_string(item)
            if text:
                cleaned.append(text)
        return cleaned
