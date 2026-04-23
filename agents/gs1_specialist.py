from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


class GS1Specialist(BaseAgent):
    """
    GS1Specialist owns:
    - identifier normalization/readiness
    - identifier plausibility checks
    - data-carrier readiness
    - resolver URL readiness
    - QR readiness (not final QR artifact)
    - identifier/data-carrier missing fields
    - print-readiness advice

    GS1Specialist does NOT own:
    - final QR image generation
    - cloud upload/public hosting
    - final resolver publication
    - product classification
    - legal/compliance truth
    - LCA/ESG values

    Important v1 limitation:
    - This agent does NOT verify GS1 authenticity or external issuance.
    - It only performs lightweight syntactic plausibility checks.
    """

    IS_MOCK = True

    def run(
        self,
        product_group: str = "textiles",
        persistent_identifier_value: str | None = None,
        operator_identifier_value: str | None = None,
        facility_identifier_value: str | None = None,
        public_resolver_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            if product_group not in {
                "textiles",
                "batteries",
                "electrical_appliances",
            }:
                raise ValueError(f"Unsupported product_group: {product_group}")

            payload = self._build_payload(
                product_group=product_group,
                persistent_identifier_value=persistent_identifier_value,
                operator_identifier_value=operator_identifier_value,
                facility_identifier_value=facility_identifier_value,
                public_resolver_url=public_resolver_url,
            )
            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)

    def _build_payload(
        self,
        product_group: str,
        persistent_identifier_value: str | None,
        operator_identifier_value: str | None,
        facility_identifier_value: str | None,
        public_resolver_url: str | None,
    ) -> AgentPayload:
        identifier_value = self._clean(persistent_identifier_value)
        operator_value = self._clean(operator_identifier_value)
        facility_value = self._clean(facility_identifier_value)
        resolver_url = self._clean(public_resolver_url)

        has_public_url = resolver_url is not None
        is_numeric_identifier = self._is_numeric_identifier(identifier_value)
        is_gs1_length_candidate = self._is_gs1_length_candidate(identifier_value)

        return {
            "domain_data": {
                "espr_core": {
                    "identifiers_hint": {
                        "persistent_unique_product_identifier": {
                            "value": identifier_value,
                            "scheme": None,
                            "format": "numeric" if is_numeric_identifier else None,
                            "issuing_body": None,
                            "check_digit_verified": None,
                        },
                        "unique_operator_identifier": {
                            "value": operator_value,
                            "scheme": None,
                            "issuing_body": None,
                        },
                        "unique_facility_identifier": {
                            "value": facility_value,
                            "scheme": None,
                            "issuing_body": None,
                        },
                    },
                    "data_carrier_hint": {
                        "type": "QR",
                        "carrier_value": resolver_url if has_public_url else None,
                        "resolver_url": resolver_url if has_public_url else None,
                        "physical_placement": "on_packaging",
                        "standard": "GS1_Digital_Link",
                        "is_persistent": has_public_url,
                        "qr_payload": resolver_url if has_public_url else None,
                        "digital_link_url": resolver_url if has_public_url else None,
                        "status": (
                            "ready_for_render"
                            if has_public_url
                            else "pending_public_url"
                        ),
                    },
                },
                "voluntary_esg": None,
                "sectoral": self._build_sectoral_passthrough(product_group),
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": None,
                "missing_fields": self._build_missing_fields(
                    identifier_value=identifier_value,
                    operator_value=operator_value,
                    facility_value=facility_value,
                    has_public_url=has_public_url,
                ),
                "warnings": self._build_warnings(
                    identifier_value=identifier_value,
                    is_numeric_identifier=is_numeric_identifier,
                    is_gs1_length_candidate=is_gs1_length_candidate,
                    has_public_url=has_public_url,
                ),
                "assumptions": [
                    (
                        "GS1/data-carrier review in v1 performs only syntactic "
                        "plausibility checks and does not prove external GS1 "
                        "authenticity or ownership."
                    ),
                    (
                        "Final QR artifact is generated later in the packaging "
                        "step after a stable public URL is available."
                    ),
                ],
                "contradictions": self._build_contradictions(
                    identifier_value=identifier_value,
                    is_numeric_identifier=is_numeric_identifier,
                    is_gs1_length_candidate=is_gs1_length_candidate,
                    has_public_url=has_public_url,
                ),
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": self._build_summary(
                    identifier_value=identifier_value,
                    operator_value=operator_value,
                    has_public_url=has_public_url,
                    is_numeric_identifier=is_numeric_identifier,
                    is_gs1_length_candidate=is_gs1_length_candidate,
                ),
                "business_risks": self._build_business_risks(
                    identifier_value=identifier_value,
                    has_public_url=has_public_url,
                    is_gs1_length_candidate=is_gs1_length_candidate,
                ),
                "recommended_next_actions": self._build_next_actions(
                    identifier_value=identifier_value,
                    operator_value=operator_value,
                    facility_value=facility_value,
                    has_public_url=has_public_url,
                    is_gs1_length_candidate=is_gs1_length_candidate,
                ),
                "supplier_requests": self._build_supplier_requests(
                    identifier_value=identifier_value,
                    operator_value=operator_value,
                ),
                "where_to_get_data": self._build_where_to_get_data(
                    has_public_url=has_public_url
                ),
                "next_batch_improvements": [
                    (
                        "Make persistent identifier assignment and stable public "
                        "resolver URL part of the release checklist before print "
                        "production."
                    ),
                    (
                        "Treat identifier authenticity as a separate verification "
                        "step from identifier formatting."
                    ),
                ],
            },
        }

    def _build_sectoral_passthrough(
        self,
        product_group: str,
    ) -> dict[str, dict[str, Any] | None]:
        # Validator-compatibility passthrough:
        # GS1Specialist does not own sectoral content, but echoes the selected
        # sector so the current validator can keep exactly-one-sectoral-block
        # semantics.
        return {
            "textiles": {} if product_group == "textiles" else None,
            "batteries": {} if product_group == "batteries" else None,
            "electrical_appliances": (
                {} if product_group == "electrical_appliances" else None
            ),
        }

    def _build_missing_fields(
        self,
        identifier_value: str | None,
        operator_value: str | None,
        facility_value: str | None,
        has_public_url: bool,
    ) -> list[dict[str, Any]]:
        missing: list[dict[str, Any]] = []

        if not identifier_value:
            missing.append(
                {
                    "field": (
                        "dpp.regulatedCore.identifiers."
                        "persistentUniqueProductIdentifier.value"
                    ),
                    "severity": "required",
                    "reason": "No persistent product identifier has been provided.",
                    "action": (
                        "Assign or provide a persistent product identifier "
                        "from product master data."
                    ),
                    "regulatory_basis": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": False,
                    "source_domain": "gs1",
                }
            )
            missing.append(
                {
                    "field": (
                        "dpp.regulatedCore.identifiers."
                        "persistentUniqueProductIdentifier.scheme"
                    ),
                    "severity": "required",
                    "reason": (
                        "Identifier scheme cannot be finalized until a "
                        "persistent product identifier exists."
                    ),
                    "action": (
                        "Choose the identifier scheme used in product master data."
                    ),
                    "regulatory_basis": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": False,
                    "source_domain": "gs1",
                }
            )

        if not operator_value:
            missing.append(
                {
                    "field": (
                        "dpp.regulatedCore.identifiers."
                        "uniqueOperatorIdentifier.value"
                    ),
                    "severity": "recommended",
                    "reason": (
                        "No operator identifier is available for the "
                        "responsible economic operator."
                    ),
                    "action": (
                        "Provide GLN, EORI, VAT, LEI, or another operator "
                        "identifier from master data."
                    ),
                    "regulatory_basis": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": False,
                    "source_domain": "gs1",
                }
            )

        if not facility_value:
            missing.append(
                {
                    "field": (
                        "dpp.regulatedCore.identifiers."
                        "uniqueFacilityIdentifier.value"
                    ),
                    "severity": "optional",
                    "reason": "No facility identifier is currently available.",
                    "action": (
                        "Add a facility identifier if plant-level traceability "
                        "is needed."
                    ),
                    "regulatory_basis": None,
                    "can_be_inferred": False,
                    "requires_supplier_confirmation": False,
                    "source_domain": "gs1",
                }
            )

        if not has_public_url:
            missing.extend(
                [
                    {
                        "field": "dpp.regulatedCore.dataCarrier.carrierValue",
                        "severity": "required",
                        "reason": (
                            "Carrier value cannot be finalized until a stable "
                            "public resolver URL exists."
                        ),
                        "action": (
                            "Publish the passport endpoint or cloud-hosted "
                            "artifact and then finalize the QR payload."
                        ),
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "gs1",
                    },
                    {
                        "field": "dpp.regulatedCore.dataCarrier.resolverUrl",
                        "severity": "required",
                        "reason": "No stable public resolver URL is available yet.",
                        "action": (
                            "Upload the final passport/package to a stable "
                            "public location and assign the resolver URL."
                        ),
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "gs1",
                    },
                    {
                        "field": "dpp.regulatedCore.dataCarrier.isPersistent",
                        "severity": "recommended",
                        "reason": (
                            "Persistence cannot be claimed until the public "
                            "URL strategy is finalized."
                        ),
                        "action": (
                            "Use a stable long-lived URL before sending the QR "
                            "to print production."
                        ),
                        "regulatory_basis": None,
                        "can_be_inferred": False,
                        "requires_supplier_confirmation": False,
                        "source_domain": "gs1",
                    },
                ]
            )

        return missing

    def _build_warnings(
        self,
        identifier_value: str | None,
        is_numeric_identifier: bool,
        is_gs1_length_candidate: bool,
        has_public_url: bool,
    ) -> list[str]:
        warnings: list[str] = []

        if not identifier_value:
            warnings.append(
                "No persistent product identifier is available; the "
                "QR/data-carrier layer cannot be finalized."
            )
        else:
            warnings.append(
                "Identifier review in v1 is only syntactic. Authenticity, "
                "ownership, and external GS1 issuance are not verified."
            )

        if is_numeric_identifier and is_gs1_length_candidate:
            warnings.append(
                "Identifier length is compatible with common GS1-family "
                "numeric keys, but check digit and registry authenticity "
                "are not verified."
            )
        elif is_numeric_identifier and not is_gs1_length_candidate:
            warnings.append(
                "Identifier is numeric but does not match common GS1-family "
                "lengths (8, 12, 13, 14)."
            )
        elif not is_numeric_identifier:
            warnings.append(
                "Identifier is non-numeric, so GS1-family numeric plausibility "
                "cannot be assessed."
            )

        if not has_public_url:
            warnings.append(
                "QR is not print-ready until a stable public resolver URL is "
                "assigned in the packaging/storage step."
            )

        return warnings

    def _build_contradictions(
        self,
        identifier_value: str | None,
        is_numeric_identifier: bool,
        is_gs1_length_candidate: bool,
        has_public_url: bool,
    ) -> list[str]:
        contradictions: list[str] = []

        if identifier_value and not has_public_url:
            contradictions.append(
                "A product identifier may be available, but no stable public "
                "resolver URL exists yet for final QR publication."
            )

        if identifier_value and is_numeric_identifier and not is_gs1_length_candidate:
            contradictions.append(
                "Identifier is present but does not match common GS1-family "
                "numeric lengths."
            )

        return contradictions

    def _build_summary(
        self,
        identifier_value: str | None,
        operator_value: str | None,
        has_public_url: bool,
        is_numeric_identifier: bool,
        is_gs1_length_candidate: bool,
    ) -> str:
        if not identifier_value:
            return (
                "GS1/data-carrier layer is not ready because no persistent "
                "product identifier is available. A final QR cannot be "
                "produced until an identifier and stable public resolver URL exist."
            )

        if not has_public_url:
            if is_numeric_identifier and is_gs1_length_candidate:
                return (
                    "A syntactically plausible numeric identifier is available, "
                    "but it remains source-unverified and QR publication is "
                    "still pending because no stable public resolver URL is assigned."
                )
            return (
                "An identifier is available, but it remains source-unverified "
                "and QR publication is still pending because no stable public "
                "resolver URL is assigned."
            )

        if not operator_value:
            return (
                "Identifier and resolver URL are partially ready, but the "
                "identifier remains source-unverified and operator "
                "identification is incomplete for stronger traceability."
            )

        return (
            "Identifier and data-carrier layer appear operationally ready for "
            "final QR rendering, but identifier authenticity remains "
            "source-unverified in v1."
        )

    def _build_business_risks(
        self,
        identifier_value: str | None,
        has_public_url: bool,
        is_gs1_length_candidate: bool,
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []

        if not identifier_value:
            risks.append(
                {
                    "title": "No persistent identifier assigned",
                    "severity": "high",
                    "why_it_matters": (
                        "Without a stable identifier, traceability and durable "
                        "passport linking are weakened from the start."
                    ),
                }
            )

        if identifier_value and not is_gs1_length_candidate:
            risks.append(
                {
                    "title": "Identifier plausibility weak",
                    "severity": "medium",
                    "why_it_matters": (
                        "An identifier with unusual format or length may block "
                        "later registry or master-data integration."
                    ),
                }
            )

        if identifier_value and not has_public_url:
            risks.append(
                {
                    "title": "QR not print-ready",
                    "severity": "medium",
                    "why_it_matters": (
                        "Printing a QR before the final public resolver URL "
                        "exists can create broken or short-lived links on "
                        "physical goods."
                    ),
                }
            )

        return risks

    def _build_next_actions(
        self,
        identifier_value: str | None,
        operator_value: str | None,
        facility_value: str | None,
        has_public_url: bool,
        is_gs1_length_candidate: bool,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        if not identifier_value:
            actions.append(
                {
                    "priority": "now",
                    "action": (
                        "Assign or confirm a persistent product identifier "
                        "from master data."
                    ),
                    "owner": "internal_compliance",
                }
            )
        elif not is_gs1_length_candidate:
            actions.append(
                {
                    "priority": "now",
                    "action": (
                        "Re-check the identifier format and confirm the exact "
                        "product code in ERP or barcode records."
                    ),
                    "owner": "brand_owner",
                }
            )

        if not operator_value:
            actions.append(
                {
                    "priority": "soon",
                    "action": (
                        "Add a unique operator identifier such as GLN, EORI, "
                        "VAT, or LEI."
                    ),
                    "owner": "brand_owner",
                }
            )

        if not facility_value:
            actions.append(
                {
                    "priority": "later",
                    "action": (
                        "Add a facility identifier if plant-level traceability "
                        "is needed."
                    ),
                    "owner": "brand_owner",
                }
            )

        if not has_public_url:
            actions.append(
                {
                    "priority": "now",
                    "action": (
                        "Publish the final passport/package to a stable public "
                        "URL before QR rendering."
                    ),
                    "owner": "internal_compliance",
                }
            )

        if identifier_value:
            actions.append(
                {
                    "priority": "soon",
                    "action": (
                        "Verify identifier authenticity and ownership against "
                        "authoritative master data or external registry sources."
                    ),
                    "owner": "internal_compliance",
                }
            )

        return actions

    def _build_supplier_requests(
        self,
        identifier_value: str | None,
        operator_value: str | None,
    ) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []

        if not identifier_value:
            requests.append(
                {
                    "request": (
                        "Provide the product identifier used in master data "
                        "or barcode records."
                    ),
                    "why_needed": (
                        "Needed to build the persistent product identifier layer."
                    ),
                    "document_type": "product_master_data_identifier",
                }
            )

        if not operator_value:
            requests.append(
                {
                    "request": "Provide the responsible operator identifier.",
                    "why_needed": (
                        "Needed to strengthen operator-level traceability in "
                        "the passport."
                    ),
                    "document_type": "operator_master_data",
                }
            )

        return requests

    def _build_where_to_get_data(self, has_public_url: bool) -> list[dict[str, Any]]:
        items = [
            {
                "missing_topic": "Persistent product identifier",
                "source": "ERP / barcode registry / product master data",
                "how_to_obtain": (
                    "Check internal product master data or barcode assignment "
                    "records for the product code in use."
                ),
            },
            {
                "missing_topic": "Operator and facility identifiers",
                "source": "company master data / compliance records / GS1 account",
                "how_to_obtain": (
                    "Retrieve operator and facility identifiers from legal "
                    "entity or site master data."
                ),
            },
        ]

        if not has_public_url:
            items.append(
                {
                    "missing_topic": "Stable public resolver URL",
                    "source": (
                        "cloud hosting / public artifact URL / passport endpoint"
                    ),
                    "how_to_obtain": (
                        "Publish the final passport or package to a stable "
                        "public location during the packaging step."
                    ),
                }
            )

        return items

    def _clean(self, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned if cleaned else None

    def _is_numeric_identifier(self, identifier_value: str | None) -> bool:
        return bool(identifier_value) and identifier_value.isdigit()

    def _is_gs1_length_candidate(self, identifier_value: str | None) -> bool:
        if not identifier_value or not identifier_value.isdigit():
            return False

        return len(identifier_value) in {8, 12, 13, 14}