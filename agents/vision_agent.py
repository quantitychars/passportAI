from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


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

    def run(
        self,
        product_group_hint: str | None = "textiles",
        image_url: str | None = None,
        sufficient_visual_evidence: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            if not sufficient_visual_evidence or product_group_hint is None:
                payload = self._build_insufficient_data_payload(image_url=image_url)
            elif product_group_hint == "textiles":
                payload = self._build_textiles_payload(image_url=image_url)
            elif product_group_hint == "batteries":
                payload = self._build_batteries_payload(image_url=image_url)
            elif product_group_hint == "electrical_appliances":
                payload = self._build_electrical_payload(image_url=image_url)
            else:
                raise ValueError(f"Unsupported product_group_hint: {product_group_hint}")

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _build_textiles_payload(self, image_url: str | None = None) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_name": "Canvas tote bag",
                    "product_description": "Light-colored textile tote bag with visible sewn label.",
                    "brand_name": "BrandName",
                    "model_name": None,
                    "model_number": None,
                    "serial_number": None,
                    "batch_lot": None,
                    "product_image_url": image_url,
                    "visible_markings": [
                        "Made in Ukraine",
                        "100% cotton",
                    ],
                    "visible_certifications": [
                        "OEKO-TEX claim visible on label",
                    ],
                    "visible_warnings": [],
                    "product_group_hint": "textiles",
                },
                "sectoral": {
                    "textiles": {
                        "care_symbols": ["wash_30", "do_not_bleach", "iron_low"],
                        "care_instructions_text": "Wash at 30°C. Do not bleach.",
                        "material_composition": [
                            {
                                "component": "body",
                                "material": "cotton",
                                "percentage": 100.0,
                                "bio_based": True,
                            }
                        ],
                        "substances_of_concern_present": None,
                        "country_of_manufacture": "UA",
                        "country_of_origin": None,
                    },
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "model_estimate",
                "confidence_score": 0.84,
                "missing_fields": [
                    {
                        "field": "image.visible_label.modelNumber",
                        "severity": "recommended",
                        "reason": "No model number is clearly visible in the uploaded image.",
                        "action": "Upload a close-up of the sewn label or packaging where model information appears.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                    {
                        "field": "image.visible_label.countryOfOrigin",
                        "severity": "recommended",
                        "reason": "Country of origin is not clearly distinguishable from the visible label text.",
                        "action": "Provide a sharper image of the label or packaging side panel.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                ],
                "warnings": [
                    "Observed certification text is treated as a visible claim, not as verified certificate validity.",
                ],
                "assumptions": [
                    "Product-group hint is based on visible textile form factor and label text.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "The image strongly suggests a textile product with readable composition and care information, but model-level identity and origin details are incomplete or not fully legible.",
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Upload a close-up photo of the full sewn label.",
                        "owner": "manufacturer",
                    },
                    {
                        "priority": "soon",
                        "action": "Provide a second image showing the back side or packaging label.",
                        "owner": "supplier",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Model and origin label details",
                        "source": "close-up photo of sewn label / packaging tag",
                        "how_to_obtain": "Capture a sharp, front-facing close-up of the internal label under good lighting.",
                    }
                ],
            },
        }

    def _build_batteries_payload(self, image_url: str | None = None) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_name": "Rechargeable battery pack",
                    "product_description": "Rectangular battery pack with technical label on casing.",
                    "brand_name": "BrandName",
                    "model_name": None,
                    "model_number": "BP-200",
                    "serial_number": "SN-784512",
                    "batch_lot": None,
                    "product_image_url": image_url,
                    "visible_markings": [
                        "CE",
                        "Li-ion",
                        "Rechargeable",
                    ],
                    "visible_certifications": [],
                    "visible_warnings": [
                        "Do not dispose in household waste",
                    ],
                    "product_group_hint": "batteries",
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": {
                        "battery_model_identifier": "BP-200",
                        "serial_number": "SN-784512",
                        "manufacturing_date": "2025-01-10",
                        "chemistry": "lithium_ion",
                        "ce_marking_present": True,
                        "label_information": {
                            "observed_text": [
                                "Li-ion",
                                "Rechargeable",
                                "CE",
                                "2025-01-10",
                            ]
                        },
                        "safety_instructions_url": None,
                    },
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "model_estimate",
                "confidence_score": 0.81,
                "missing_fields": [
                    {
                        "field": "image.visible_label.batteryChemistry",
                        "severity": "recommended",
                        "reason": "Battery chemistry appears visible but should be confirmed with a sharper close-up for OCR certainty.",
                        "action": "Upload a close-up of the battery casing label with higher resolution.",
                        "regulatory_basis": None,
                        "can_be_inferred": True,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                    {
                        "field": "image.visible_label.capacityOrVoltage",
                        "severity": "recommended",
                        "reason": "Capacity and voltage values are not reliably readable from the current image.",
                        "action": "Provide a tighter image crop of the specification label.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                ],
                "warnings": [
                    "Battery category and passport obligation cannot be concluded from appearance alone.",
                ],
                "assumptions": [
                    "Product-group hint is based on visible battery casing and label language.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "The image suggests a battery product with visible CE and chemistry markings, but several technical fields remain unreadable or visually unconfirmed.",
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Upload a close-up of the battery technical label.",
                        "owner": "manufacturer",
                    },
                    {
                        "priority": "soon",
                        "action": "Provide an image of the opposite side of the battery pack if additional markings are present.",
                        "owner": "supplier",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Battery technical label details",
                        "source": "close-up photo of battery casing / label",
                        "how_to_obtain": "Capture the battery casing label straight-on with high contrast and good lighting.",
                    }
                ],
                "business_risks": [
                    {
                        "title": "Insufficient visual evidence for battery specifics",
                        "severity": "medium",
                        "why_it_matters": "Unreadable technical markings may block downstream classification and evidence validation.",
                    }
                ],
            },
        }

    def _build_electrical_payload(self, image_url: str | None = None) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_name": "Compact washing machine",
                    "product_description": "Front-loading appliance with visible control panel and partial energy label.",
                    "brand_name": "BrandName",
                    "model_name": None,
                    "model_number": "WM-500",
                    "serial_number": None,
                    "batch_lot": None,
                    "product_image_url": image_url,
                    "visible_markings": [
                        "Energy label visible",
                        "Front-load washing machine",
                    ],
                    "visible_certifications": [],
                    "visible_warnings": [],
                    "product_group_hint": "electrical_appliances",
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": {
                        "appliance_type": "washing_machine",
                        "energy_class": "B",
                        "user_manual_url": None,
                        "installation_manual_url": None,
                        "contains_battery": False,
                        "repair_instructions_url": None,
                    },
                },
            },
            "assessment": {
                "confidence_source": "model_estimate",
                "confidence_score": 0.79,
                "missing_fields": [
                    {
                        "field": "image.visible_label.energyLabel",
                        "severity": "recommended",
                        "reason": "Energy label is partially visible but not fully readable.",
                        "action": "Upload a front-facing close-up of the full energy label.",
                        "regulatory_basis": None,
                        "can_be_inferred": True,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                    {
                        "field": "image.visible_label.userManualUrl",
                        "severity": "optional",
                        "reason": "No documentation URL is visibly readable in the current image.",
                        "action": "Provide a photo of packaging, documentation, or rear label where support URLs may appear.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    },
                ],
                "warnings": [
                    "Observed appliance type is a visual hint and should not be treated as final regulatory classification.",
                ],
                "assumptions": [
                    "Appliance type hint is based on visible front-loading form factor and control layout.",
                ],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "The image suggests an electrical appliance, likely a washing machine, with a partially visible energy label, but supporting label and documentation evidence remain incomplete.",
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Upload a straight-on close-up of the full energy label.",
                        "owner": "manufacturer",
                    },
                    {
                        "priority": "soon",
                        "action": "Provide rear-label and packaging photos for model and documentation details.",
                        "owner": "supplier",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Energy label and support URLs",
                        "source": "front label / rear sticker / packaging / manual cover",
                        "how_to_obtain": "Capture separate close-up images of the energy label and rear specification sticker.",
                    }
                ],
            },
        }

    def _build_insufficient_data_payload(self, image_url: str | None = None) -> AgentPayload:
        return {
            "domain_data": {
                "espr_core": {
                    "product_name": None,
                    "product_description": "Image evidence is insufficient for reliable product identification.",
                    "brand_name": None,
                    "model_name": None,
                    "model_number": None,
                    "serial_number": None,
                    "batch_lot": None,
                    "product_image_url": image_url,
                    "visible_markings": [],
                    "visible_certifications": [],
                    "visible_warnings": [],
                    "product_group_hint": None,
                },
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": 0.18,
                "missing_fields": [
                    {
                        "field": "image.visible_label.productIdentity",
                        "severity": "required",
                        "reason": "The uploaded image does not provide enough readable evidence to identify the product or its labels.",
                        "action": "Upload a clearer product image plus close-up label shots.",
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "vision",
                    }
                ],
                "warnings": [
                    "Image quality or framing is insufficient for reliable OCR and visual extraction.",
                ],
                "assumptions": [],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "The current image does not provide enough visual evidence for reliable extraction. A clearer front view and close-up label images are needed before downstream validation.",
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "action": "Upload a sharper front-facing product photo.",
                        "owner": "manufacturer",
                    },
                    {
                        "priority": "now",
                        "action": "Upload close-up images of all visible labels, markings, and packaging text.",
                        "owner": "supplier",
                    },
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "Readable visual evidence",
                        "source": "front view, rear label, packaging, close-up OCR shots",
                        "how_to_obtain": "Retake photos under good lighting, with the label filling most of the frame and no motion blur.",
                    }
                ],
                "business_risks": [
                    {
                        "title": "Visual evidence insufficient for downstream extraction",
                        "severity": "medium",
                        "why_it_matters": "Weak image evidence can block reliable classification, document matching, and passport completeness checks.",
                    }
                ],
            },
        }