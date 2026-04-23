from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class LCASpecialist(BaseAgent):
    """
    LCASpecialist owns:
    - environmental provenance review
    - sustainability data-quality review
    - environmental missing fields
    - supplier data requests
    - next-batch sustainability advice
    - optional pass-through declared ESG data

    LCASpecialist does NOT own:
    - invented GWP values
    - proxy lookup-table values
    - guessed recycled-content percentages
    - regulatory requiredness
    - legal document truth
    - product classification
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
                "espr_core": {},
                "voluntary_esg": None,
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": None,
                "missing_fields": [
                    {
                        "field": "dpp.voluntaryEsg.footprint.carbonFootprint.gwpKgCo2e",
                        "severity": "recommended",
                        "reason": "No declared or supplier-backed carbon-footprint data is available for the textile product.",
                        "action": "Request supplier footprint data or a product-level environmental declaration before making sustainability claims.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.footprint.waterConsumption.litersPerUnit",
                        "severity": "optional",
                        "reason": "No product-specific water-consumption data is available.",
                        "action": "Request any environmental declaration or process-water disclosure from the supplier if this metric is important for reporting.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.recycledContent.overallPercentage",
                        "severity": "recommended",
                        "reason": "No declared recycled-content evidence is available.",
                        "action": "Request a recycled-content declaration or supporting certificate from the supplier.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.packaging.material",
                        "severity": "optional",
                        "reason": "Packaging sustainability data is missing.",
                        "action": "Request packaging material, recyclability, and recycled-content details.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.supplyChainTransparency.transparencyLevel",
                        "severity": "optional",
                        "reason": "No supply-chain transparency statement is available.",
                        "action": "Request at least tier-1 supplier transparency information.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                ],
                "warnings": [
                    "No environmental values should be published as fact until supplier-backed sustainability data is provided.",
                ],
                "assumptions": [
                    "No reliable footprint, recycled-content, or packaging dataset has been provided for this textile product.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "No reliable textile sustainability data is currently available. The product should be treated as environmentally undocumented rather than environmentally measured.",
                "business_risks": [
                    {
                        "title": "Unsupported sustainability positioning",
                        "severity": "medium",
                        "why_it_matters": "Environmental claims without product-backed data may mislead customers or weaken trust in the passport.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request supplier environmental declarations for footprint, recycled content, and packaging.",
                        "owner": "supplier",
                    }
                ],
                "supplier_requests": [
                    {
                        "request": "Provide carbon-footprint or environmental declaration for the textile product.",
                        "why_needed": "Needed to populate voluntary sustainability information honestly.",
                        "document_type": "environmental_declaration",
                    },
                    {
                        "request": "Provide recycled-content declaration and packaging specification.",
                        "why_needed": "Needed for recycled-content and packaging sustainability fields.",
                        "document_type": "recycled_content_or_packaging_declaration",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Textile sustainability data",
                        "source": "supplier environmental declaration / packaging specification / recycled-content statement",
                        "how_to_obtain": "Ask the supplier for product-specific sustainability documentation tied to the SKU or model.",
                    }
                ],
                "next_batch_improvements": [
                    "Collect environmental declarations and packaging specifications during supplier onboarding instead of after passport generation starts.",
                ],
            },
        }

    def _build_batteries_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {},
                "voluntary_esg": None,
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": None,
                "missing_fields": [
                    {
                        "field": "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint",
                        "severity": "required",
                        "reason": "No battery-specific carbon-footprint declaration is available.",
                        "action": "Request the battery carbon-footprint declaration and supporting methodology or verification references.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials",
                        "severity": "required",
                        "reason": "No declared critical raw materials breakdown is available.",
                        "action": "Request CRM composition and source-country data from the battery manufacturer.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent",
                        "severity": "required",
                        "reason": "No supplier-backed recycled-content evidence is available for the battery materials.",
                        "action": "Request recycled-content declarations and supporting evidence from the battery manufacturer.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.packaging.material",
                        "severity": "optional",
                        "reason": "Packaging sustainability data is missing.",
                        "action": "Request packaging material and recyclability information from the supplier or packager.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                ],
                "warnings": [
                    "Battery sustainability values should not be invented or estimated without source-backed evidence.",
                ],
                "assumptions": [
                    "No battery sustainability dossier has been provided for this product.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Battery sustainability data is absent. The passport can identify the product, but its environmental layer is incomplete until manufacturer-backed sustainability documentation is attached.",
                "business_risks": [
                    {
                        "title": "Battery sustainability layer unsupported",
                        "severity": "high",
                        "why_it_matters": "Battery sustainability fields are high-sensitivity data points and should not be represented without source-backed declarations.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request battery carbon-footprint, critical raw materials, and recycled-content declarations.",
                        "owner": "supplier",
                    }
                ],
                "supplier_requests": [
                    {
                        "request": "Provide battery sustainability dossier including carbon footprint, CRM, and recycled content.",
                        "why_needed": "Needed to populate the battery sustainability/composition layer credibly.",
                        "document_type": "battery_sustainability_dossier",
                    }
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Battery sustainability declarations",
                        "source": "battery manufacturer sustainability / technical documentation pack",
                        "how_to_obtain": "Ask the battery manufacturer for product-specific sustainability documents tied to the battery model.",
                    }
                ],
                "next_batch_improvements": [
                    "Require battery sustainability declarations before approving a new battery product for passport publication.",
                ],
            },
        }

    def _build_electrical_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {},
                "voluntary_esg": None,
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": None,
                "missing_fields": [
                    {
                        "field": "dpp.voluntaryEsg.footprint.carbonFootprint.gwpKgCo2e",
                        "severity": "recommended",
                        "reason": "No product-specific carbon-footprint data is available for the appliance.",
                        "action": "Request environmental declaration, BOM-backed footprint information, or equivalent sustainability documentation.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.recycledContent.overallPercentage",
                        "severity": "optional",
                        "reason": "No declared recycled-content evidence is available for the appliance.",
                        "action": "Request recycled-content declarations or BOM-backed material information.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.sectoralElectricalAppliance.materialsAndSubstances.materialCompositionSummary",
                        "severity": "recommended",
                        "reason": "No material composition summary is available from BOM or supplier documentation.",
                        "action": "Request component or material breakdown for the appliance.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                    {
                        "field": "dpp.voluntaryEsg.packaging.material",
                        "severity": "optional",
                        "reason": "Packaging sustainability data is missing.",
                        "action": "Request packaging material, recyclability, and recycled-content information.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "lca",
                    },
                ],
                "warnings": [
                    "Environmental values for the appliance should not be represented as known facts without supporting sustainability documentation.",
                ],
                "assumptions": [
                    "No product-specific environmental declaration or BOM has been provided.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Electrical appliance sustainability data is missing. Environmental communication should remain conservative until BOM-backed or supplier-declared evidence is available.",
                "business_risks": [
                    {
                        "title": "Weak evidence for appliance sustainability messaging",
                        "severity": "medium",
                        "why_it_matters": "Without BOM or supplier declarations, sustainability messaging around the appliance may be unsupported.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request BOM or material breakdown and any product-level environmental declaration.",
                        "owner": "supplier",
                    }
                ],
                "supplier_requests": [
                    {
                        "request": "Provide BOM or material composition summary for the appliance.",
                        "why_needed": "Needed to support material and environmental data in the passport.",
                        "document_type": "bom_or_material_declaration",
                    },
                    {
                        "request": "Provide packaging sustainability declaration.",
                        "why_needed": "Needed for voluntary packaging sustainability fields.",
                        "document_type": "packaging_declaration",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Appliance environmental data",
                        "source": "supplier BOM / product environmental declaration / packaging specification",
                        "how_to_obtain": "Ask the supplier for model-specific BOM, packaging data, and any available environmental declaration.",
                    }
                ],
                "next_batch_improvements": [
                    "Make BOM and packaging declarations standard supplier onboarding requirements for electrical products.",
                ],
            },
        }