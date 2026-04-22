from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class RegulatoryConsultant(BaseAgent):
    """
    RegulatoryConsultant owns:
    - classification
    - sector applicability
    - requiredness
    - legal basis
    - regulatory interpretation
    - regulatory gaps
    - regulatory advice

    RegulatoryConsultant does NOT own:
    - measurements
    - supplier-verified numeric facts
    - QR / GS1 identifiers
    - legal document internals
    - vision evidence
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
                    "product_group": "textiles",
                    "sector_profile": {
                        "name": "textile_core_v1",
                        "version": "1.0.0",
                        "regulatory_source": [
                            "REG_2024_1781_ESPR",
                            "SECTORAL_ACT_PENDING",
                        ],
                    },
                    "espr_category": "textiles",
                    "granularity_level": "model",
                    "legal_basis": [
                        "ESPR_2024_1781",
                    ],
                    "cn_code": None,
                },
                "sectoral": {
                    "textiles": {
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
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.93,
                "missing_fields": [
                    {
                        "field": "dpp.regulatedCore.productIdentity.cnCode",
                        "severity": "required",
                        "reason": "CN code is needed to support product classification and customs-facing product identification.",
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
                        "reason": "Care symbols improve usability and strengthen passport completeness for textile products.",
                        "action": "Collect care label information from the physical label or supplier technical sheet.",
                        "regulatory_basis": "SECTORAL_ACT_PENDING",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "regulatory",
                    },
                ],
                "warnings": [
                    "Textile sector requirements may evolve as sectoral delegated acts mature.",
                ],
                "assumptions": [
                    "Product is treated as a textile article for regulatory profiling.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Classified as textiles under the textile_core_v1 regulatory profile. The main blockers are missing CN code, missing material composition, and incomplete care/manufacturing information.",
                "business_risks": [
                    {
                        "title": "Incomplete textile identity data",
                        "severity": "high",
                        "why_it_matters": "Publishing a passport without confirmed composition and classification data can weaken compliance readiness and downstream traceability.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request a textile composition sheet with component percentages.",
                        "owner": "supplier",
                    },
                    {
                        "priority": "now",
                        "action": "Confirm the CN code and legal basis with compliance documentation.",
                        "owner": "internal_compliance",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide material composition by component and percentage.",
                        "why_needed": "Needed for textile sector composition requirements.",
                        "document_type": "composition_sheet",
                    },
                    {
                        "request": "Provide manufacturing country and care label data.",
                        "why_needed": "Needed for textile manufacturing and care fields.",
                        "document_type": "technical_specification",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "CN code",
                        "source": "customs documentation / importer compliance file",
                        "how_to_obtain": "Check customs classification documents or ask the importer/compliance owner.",
                    }
                ],
                "next_batch_improvements": [
                    "Require composition sheets and care label data from suppliers before onboarding a new textile SKU.",
                ],
            },
        }

    def _build_batteries_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_group": "batteries",
                    "sector_profile": {
                        "name": "battery_passport_annex_xiii_v1",
                        "version": "1.0.0",
                        "regulatory_source": [
                            "REG_2023_1542_BATTERIES",
                        ],
                    },
                    "espr_category": "batteries",
                    "granularity_level": "model",
                    "legal_basis": [
                        "BATTERY_REG_2023_1542",
                    ],
                    "cn_code": None,
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": {
                        "battery_category": None,
                        "chemistry": None,
                        "is_rechargeable": None,
                        "passport_required": True,
                        "passport_requirement_basis": "ARTICLE_77_BATTERY_REGULATION",
                        "ce_marking_present": None,
                    },
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.95,
                "missing_fields": [
                    {
                        "field": "dpp.sectoralBattery.batteryClassification.batteryCategory",
                        "severity": "critical",
                        "reason": "Battery category is required to determine the applicable passport obligations.",
                        "action": "Confirm whether the battery is portable, industrial, EV, LMT, or SLI.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "regulatory",
                    },
                    {
                        "field": "dpp.sectoralBattery.batteryClassification.chemistry",
                        "severity": "required",
                        "reason": "Battery chemistry is a key sectoral classification field.",
                        "action": "Request the battery chemistry declaration from the manufacturer or technical datasheet.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "regulatory",
                    },
                    {
                        "field": "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint",
                        "severity": "required",
                        "reason": "Battery carbon footprint data is required by the battery passport framework, even though its value must come from other evidence sources.",
                        "action": "Obtain the battery carbon footprint declaration or supporting technical documentation.",
                        "regulatory_basis": "BATTERY_REG_2023_1542",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": True,
                        "source_domain": "regulatory",
                    },
                ],
                "warnings": [
                    "Battery passport readiness depends on both regulatory classification and sector-specific evidence from technical sources.",
                ],
                "assumptions": [
                    "Product is treated as a battery subject to battery passport requirements.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Classified as batteries under the battery_passport_annex_xiii_v1 profile. The main blockers are unresolved battery category, chemistry, and battery-passport-required sustainability fields.",
                "business_risks": [
                    {
                        "title": "Battery category or chemistry not confirmed",
                        "severity": "high",
                        "why_it_matters": "Incorrect classification can lead to the wrong passport structure and missing mandatory battery data.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Request official battery chemistry and category documentation.",
                        "owner": "supplier",
                    },
                    {
                        "priority": "now",
                        "action": "Confirm whether the product falls under Article 77 battery passport obligations.",
                        "owner": "internal_compliance",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide battery chemistry, category, and manufacturing date.",
                        "why_needed": "Needed to establish battery passport classification.",
                        "document_type": "technical_datasheet",
                    },
                    {
                        "request": "Provide carbon footprint declaration for the battery passport.",
                        "why_needed": "Needed for battery sustainability and composition fields.",
                        "document_type": "battery_passport_supporting_document",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Battery chemistry and category",
                        "source": "manufacturer technical datasheet",
                        "how_to_obtain": "Ask the battery manufacturer or authorized supplier for the declared chemistry and battery class.",
                    }
                ],
                "next_batch_improvements": [
                    "Require battery chemistry, category, and passport-related sustainability documents before procurement approval.",
                ],
            },
        }

    def _build_electrical_payload(self) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_group": "electrical_appliances",
                    "sector_profile": {
                        "name": "electrical_appliance_espr_ready_v1",
                        "version": "1.0.0",
                        "regulatory_source": [
                            "REG_2024_1781_ESPR",
                            "REG_2017_1369_ENERGY_LABELLING",
                            "SECTORAL_ACT_PENDING",
                        ],
                    },
                    "espr_category": "electrical_appliances",
                    "granularity_level": "model",
                    "legal_basis": [
                        "ESPR_2024_1781",
                        "ENERGY_LABELLING_2017_1369",
                    ],
                    "cn_code": None,
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": {
                        "appliance_type": None,
                        "energy_related_product": None,
                        "energy_label_required": None,
                        "eprel_registered": None,
                        "repairability_applicable": True,
                        "service_information_available": None,
                        "contains_battery": None,
                    },
                },
            },
            "assessment": {
                "confidence_source": "regulation_text",
                "confidence_score": 0.91,
                "missing_fields": [
                    {
                        "field": "dpp.sectoralElectricalAppliance.applianceClassification.applianceType",
                        "severity": "critical",
                        "reason": "Appliance type is needed to choose the correct sectoral interpretation and expected evidence set.",
                        "action": "Confirm the appliance type from the product technical documentation.",
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
                        "reason": "User-facing documentation improves operational completeness and serviceability.",
                        "action": "Collect the user manual URL or upload a manual asset.",
                        "regulatory_basis": "SECTORAL_ACT_PENDING",
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "regulatory",
                    },
                ],
                "warnings": [
                    "Electrical appliance requirements may vary depending on the final confirmed product class and applicable energy-labelling obligations.",
                ],
                "assumptions": [
                    "Product is treated as an electrical appliance within the ESPR-ready profile.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Classified as electrical_appliances under the electrical_appliance_espr_ready_v1 profile. The main blockers are unresolved appliance type, energy-labelling status, and missing documentation links.",
                "business_risks": [
                    {
                        "title": "Wrong appliance classification or energy-labelling scope",
                        "severity": "high",
                        "why_it_matters": "If the appliance type or label scope is wrong, the passport may omit mandatory sector-specific fields.",
                    }
                ],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Confirm the appliance type and whether energy-labelling obligations apply.",
                        "owner": "internal_compliance",
                    },
                    {
                        "priority": "soon",
                        "action": "Request official energy label or EPREL evidence from the supplier.",
                        "owner": "supplier",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide the appliance classification and product technical datasheet.",
                        "why_needed": "Needed to confirm regulatory product type and expected passport fields.",
                        "document_type": "technical_datasheet",
                    },
                    {
                        "request": "Provide the energy label / EPREL evidence and user manual.",
                        "why_needed": "Needed for energy and documentation fields.",
                        "document_type": "energy_label_or_manual",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Energy class and label status",
                        "source": "supplier technical file / energy label evidence / EPREL registration evidence",
                        "how_to_obtain": "Ask the manufacturer or importer for the official label evidence and registration identifiers.",
                    }
                ],
                "next_batch_improvements": [
                    "Require energy-label evidence, manuals, and appliance classification data before listing a new electrical product.",
                ],
            },
        }