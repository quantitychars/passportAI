from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class LegalAgent(BaseAgent):
    """
    LegalAgent owns:
    - documentary compliance status
    - declaration / technical documentation presence
    - claim substantiation status
    - access / disclosure guidance
    - legal gaps
    - legal risks
    - human-review triggers

    LegalAgent does NOT own:
    - final product classification
    - sector profile selection
    - visual evidence / OCR extraction
    - GS1 identifiers
    - LCA calculations
    - numeric product measurements
    - supplier-confirmed technical facts without documents
    """

    IS_MOCK = True

    def run(self, product_group: str = "textiles", **kwargs: Any) -> dict[str, Any]:
        try:
            if product_group == "textiles":
                payload = self._build_textiles_payload()
            elif product_group == "batteries":
                payload = self._build_batteries_payload()
            elif product_group == "electrical_appliances":
                payload = self._build_electrical_payload()
            else:
                raise ValueError(f"Unsupported product_group: {product_group}")

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _build_textiles_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "compliance_hint": {
                        "declaration_of_conformity": {
                            "required": False,
                            "present": False,
                            "document_url": None,
                            "document_reference": None,
                        },
                        "technical_documentation": {
                            "present": False,
                            "document_reference": None,
                            "document_url": None,
                            "storage_location": "internal",
                            "last_updated": None,
                        },
                        "access_control": {
                            "public_sections": [
                                "product identity",
                                "care and use",
                                "basic material composition",
                            ],
                            "restricted_sections": {
                                "market_surveillance_authorities": [
                                    "full technical file",
                                    "chemical declarations",
                                ],
                                "customs": [
                                    "classification support documents",
                                ],
                                "economic_operators": [
                                    "supplier declarations",
                                ],
                            },
                            "confidential_business_information": [
                                "supplier commercial terms",
                            ],
                        },
                        "claim_review": {
                            "unsupported_claims": [
                                "OEKO-TEX claim visible but not document-backed",
                            ],
                            "document_backed_claims": [],
                            "needs_claim_substantiation": True,
                        },
                    }
                },
                "sectoral": {
                    "textiles": {
                        "substances_of_concern_present": None,
                        "certifications": [],
                    },
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.89,
                "missing_fields": [
                    {
                        "field": "dpp.regulatedCore.compliance.technicalDocumentation",
                        "severity": "required",
                        "reason": "Technical documentation is not attached or referenced.",
                        "action": "Request a technical file reference or upload the supporting technical documentation.",
                        "regulatory_basis": "ESPR_2024_1781",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.sectoralTextile.certificationAndClaims.certifications",
                        "severity": "recommended",
                        "reason": "A visible certification claim exists, but no certificate reference or supporting document is attached.",
                        "action": "Request the certificate PDF, certificate number, issuer, and validity dates before publishing the claim.",
                        "regulatory_basis": "SECTORAL_ACT_PENDING",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.sectoralTextile.substances",
                        "severity": "required",
                        "reason": "No documentary statement is available for substances of concern / chemical compliance.",
                        "action": "Request a chemical declaration or REACH/SVHC statement from the supplier.",
                        "regulatory_basis": "ESPR_2024_1781",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                ],
                "warnings": [
                    "Visible certification claims must not be treated as verified legal truth without supporting documents.",
                ],
                "assumptions": [
                    "Textile compliance evaluation is based on document availability, not on visual claims alone.",
                ],
                "contradictions": [
                    "Certification-related claim may be present in product evidence, but no certificate file is attached.",
                ],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "The textile product may be passportable, but documentary compliance is incomplete. Certification claims and chemical/substances-related compliance need supporting documents before public publication.",
                "business_risks": [
                    {
                        "title": "Unsupported certification claim",
                        "severity": "high",
                        "why_it_matters": "Publishing a certification claim without documentary substantiation creates claim-risk and weakens trust in the passport.",
                    },
                    {
                        "title": "No technical documentation reference",
                        "severity": "medium",
                        "why_it_matters": "Missing technical documentation reduces defensibility during review, audit, or authority requests.",
                    },
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request a certificate PDF and certificate number for any visible certification claim.",
                        "owner": "supplier",
                    },
                    {
                        "priority": "now",
                        "action": "Request a chemical compliance / substances declaration for the textile product.",
                        "owner": "supplier",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide certification documents for all visible environmental or quality claims.",
                        "why_needed": "Needed to substantiate textile certification claims in the passport.",
                        "document_type": "certificate_pdf",
                    },
                    {
                        "request": "Provide a chemical declaration / REACH-SVHC statement.",
                        "why_needed": "Needed to support substances-related compliance fields.",
                        "document_type": "chemical_declaration",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Certification substantiation",
                        "source": "supplier compliance pack / certificate issuer documentation",
                        "how_to_obtain": "Ask the supplier for the certificate PDF, certificate number, issuer, scope, and validity dates.",
                    },
                    {
                        "missing_topic": "Substances compliance",
                        "source": "supplier chemical declaration / REACH statement",
                        "how_to_obtain": "Request a formal chemical compliance declaration that names the product or SKU.",
                    },
                ],
                "next_batch_improvements": [
                    "Require certificates and chemical declarations during supplier onboarding, not after passport assembly starts.",
                ],
            },
        }

    def _build_batteries_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "compliance_hint": {
                        "declaration_of_conformity": {
                            "required": True,
                            "present": False,
                            "document_url": None,
                            "document_reference": None,
                        },
                        "technical_documentation": {
                            "present": False,
                            "document_reference": None,
                            "document_url": None,
                            "storage_location": "internal",
                            "last_updated": None,
                        },
                        "access_control": {
                            "public_sections": [
                                "product identity",
                                "basic battery information",
                            ],
                            "restricted_sections": {
                                "market_surveillance_authorities": [
                                    "full battery technical file",
                                    "conformity evidence",
                                ],
                                "customs": [
                                    "product classification support",
                                ],
                                "economic_operators": [
                                    "manufacturer declarations",
                                ],
                            },
                            "confidential_business_information": [
                                "internal compliance notes",
                            ],
                        },
                        "claim_review": {
                            "unsupported_claims": [],
                            "document_backed_claims": [],
                            "needs_claim_substantiation": True,
                        },
                    }
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": {
                        "declaration_of_conformity_reference": None,
                        "technical_documentation_reference": None,
                    },
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.94,
                "missing_fields": [
                    {
                        "field": "dpp.regulatedCore.compliance.declarationOfConformity",
                        "severity": "critical",
                        "reason": "Declaration of Conformity is required but not present or referenced.",
                        "action": "Request the Declaration of Conformity from the manufacturer or importer before publication.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.regulatedCore.compliance.technicalDocumentation",
                        "severity": "required",
                        "reason": "Battery technical documentation is not attached or referenced.",
                        "action": "Request the battery technical documentation reference or upload the relevant file.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.sectoralBattery.conformityAndInformation.declarationOfConformityReference",
                        "severity": "required",
                        "reason": "The sector-specific conformity reference is missing.",
                        "action": "Attach the declaration reference used to substantiate battery conformity information.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                ],
                "warnings": [
                    "Battery products should not be published with conformity implications unless the relevant declaration and technical references are available.",
                ],
                "assumptions": [
                    "Battery legal review is based on expected documentary conformity requirements.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Battery documentary compliance is incomplete. The main blockers are missing Declaration of Conformity and missing technical documentation references needed to support conformity-related passport fields.",
                "business_risks": [
                    {
                        "title": "Missing conformity documentation",
                        "severity": "high",
                        "why_it_matters": "A battery passport that implies conformity without supporting declarations creates a material compliance risk.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request the Declaration of Conformity from the manufacturer or importer.",
                        "owner": "supplier",
                    },
                    {
                        "priority": "now",
                        "action": "Request the technical documentation reference for the battery product.",
                        "owner": "supplier",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide Declaration of Conformity for the battery product.",
                        "why_needed": "Needed to substantiate conformity-related passport statements.",
                        "document_type": "declaration_of_conformity",
                    },
                    {
                        "request": "Provide battery technical documentation reference.",
                        "why_needed": "Needed to support the technical documentation block.",
                        "document_type": "technical_document_reference",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Battery conformity documents",
                        "source": "manufacturer compliance file / importer documentation pack",
                        "how_to_obtain": "Ask the manufacturer or importer for the formal Declaration of Conformity and technical file reference.",
                    }
                ],
                "next_batch_improvements": [
                    "Require conformity documents in the procurement package before accepting a new battery product into the catalog.",
                ],
            },
        }

    def _build_electrical_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "compliance_hint": {
                        "declaration_of_conformity": {
                            "required": True,
                            "present": False,
                            "document_url": None,
                            "document_reference": None,
                        },
                        "technical_documentation": {
                            "present": False,
                            "document_reference": None,
                            "document_url": None,
                            "storage_location": "internal",
                            "last_updated": None,
                        },
                        "access_control": {
                            "public_sections": [
                                "product identity",
                                "basic user-facing documentation",
                            ],
                            "restricted_sections": {
                                "market_surveillance_authorities": [
                                    "full technical documentation",
                                ],
                                "customs": [
                                    "classification support documents",
                                ],
                                "economic_operators": [
                                    "manufacturer declarations",
                                ],
                            },
                            "confidential_business_information": [
                                "internal technical assessments",
                            ],
                        },
                        "claim_review": {
                            "unsupported_claims": [
                                "Energy-related or repairability claims may be present without supporting documentation.",
                            ],
                            "document_backed_claims": [],
                            "needs_claim_substantiation": True,
                        },
                    }
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": {
                        "technical_documentation_reference": None,
                    },
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.9,
                "missing_fields": [
                    {
                        "field": "dpp.regulatedCore.compliance.declarationOfConformity",
                        "severity": "critical",
                        "reason": "Declaration of Conformity is expected but not present or referenced.",
                        "action": "Request the Declaration of Conformity before treating the product as publication-ready.",
                        "regulatory_basis": "ESPR_2024_1781",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.regulatedCore.compliance.technicalDocumentation",
                        "severity": "required",
                        "reason": "Technical documentation reference is missing.",
                        "action": "Request the technical documentation reference or upload a compliant supporting document.",
                        "regulatory_basis": "ESPR_2024_1781",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                    {
                        "field": "dpp.sectoralElectricalAppliance.documentationAndSoftware.technicalDocumentationReference",
                        "severity": "required",
                        "reason": "Sector-specific documentation reference is missing for the electrical appliance profile.",
                        "action": "Attach a technical documentation reference tied to the model or SKU.",
                        "regulatory_basis": "SECTORAL_ACT_PENDING",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "legal",
                    },
                ],
                "warnings": [
                    "Documentation-backed support is needed before presenting energy, repairability, or compliance claims as trustworthy passport facts.",
                ],
                "assumptions": [
                    "Electrical appliance legal review is based on expected documentation and declaration requirements.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Electrical appliance documentary compliance is incomplete. The passport should not be treated as publication-ready until declaration and technical documentation references are attached.",
                "business_risks": [
                    {
                        "title": "Unsupported compliance or energy-related claims",
                        "severity": "high",
                        "why_it_matters": "Claims presented without documentary substantiation create compliance and credibility risk.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request the Declaration of Conformity and technical documentation reference.",
                        "owner": "supplier",
                    },
                    {
                        "priority": "soon",
                        "action": "Remove or mark unsupported documentation-sensitive claims as unverified until documents are attached.",
                        "owner": "internal_compliance",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide Declaration of Conformity for the electrical appliance.",
                        "why_needed": "Needed to support core compliance status.",
                        "document_type": "declaration_of_conformity",
                    },
                    {
                        "request": "Provide technical documentation reference tied to the model or SKU.",
                        "why_needed": "Needed for documentation and software compliance layer.",
                        "document_type": "technical_document_reference",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Compliance documentation",
                        "source": "manufacturer technical file / importer compliance pack",
                        "how_to_obtain": "Ask the manufacturer or importer for the declaration and technical file reference for the exact model.",
                    }
                ],
                "next_batch_improvements": [
                    "Make conformity documents and model-specific technical references mandatory before new electrical products are listed.",
                ],
            },
        }