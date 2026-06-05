from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.base_agent import BaseAgent


_SUPPORTED_PRODUCT_GROUPS = {"batteries", "electrical_appliances", "textiles"}

_REQUIRED_IDENTIFIER_FIELDS = {
    "persistent_product_identifier": "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.value",
    "operator_identifier": "dpp.regulatedCore.identifiers.uniqueOperatorIdentifier.value",
    "resolver_url": "dpp.regulatedCore.dataCarrier.resolverUrl",
    "carrier_value": "dpp.regulatedCore.dataCarrier.carrierValue",
}


@dataclass(frozen=True)
class IdentifierCheck:
    field: str
    severity: str
    blocking: bool
    reason: str
    action: str
    owner_hint: str
    regulatory_basis: str | None = None

    def as_gap(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "severity": self.severity,
            "blocking": self.blocking,
            "reason_code": "missing",
            "reason": self.reason,
            "why_it_matters": (
                "A Digital Product Passport needs stable identifiers and a resolvable "
                "data carrier so the product, operator, and online passport can be "
                "linked reliably."
            ),
            "current_evidence_status": "absent",
            "evidence_source": "missing",
            "acceptable_evidence": [
                "product master data",
                "GS1 registry export",
                "ERP export",
                "operator master-data record",
                "public resolver URL",
            ],
            "where_to_get_data": (
                "product master data, GS1 account, ERP/PIM system, or the public "
                "passport hosting configuration"
            ),
            "closure_condition": (
                "Provide a stable identifier or resolver value from an authoritative "
                "system and rerun the audit."
            ),
            "action": self.action,
            "owner_hint": self.owner_hint,
            "source_agents": ["GS1Specialist"],
            "requires_supplier_confirmation": False,
            "regulatory_basis": self.regulatory_basis,
        }


class GS1Specialist(BaseAgent):
    """Deterministic identifier, resolver, and data-carrier readiness checks.

    This agent intentionally does not use an LLM by default. Identifier plausibility,
    GTIN check digits, resolver URL presence, and QR readiness are rule-based checks.
    Optional wording can be added later, but deterministic checks remain the source
    of truth.
    """

    AGENT_NAME = "GS1Specialist"

    def run(
        self,
        *,
        product_group: str | None = None,
        product_input: dict[str, Any] | None = None,
        reconciled_domain_data: dict[str, Any] | None = None,
        public_package_url: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        group = self._normalize_product_group(product_group, product_input, reconciled_domain_data)
        if group not in _SUPPORTED_PRODUCT_GROUPS:
            return self._fail_closed(
                product_group=group,
                reason=(
                    "Unsupported or unknown product group for identifier and data-carrier "
                    "readiness checks."
                ),
            )

        source = self._build_source(
            product_input=product_input or {},
            reconciled_domain_data=reconciled_domain_data or {},
            public_package_url=public_package_url,
        )

        identifiers = self._extract_identifier_values(source)
        gaps = self._build_identifier_gaps(identifiers, group)
        warnings = self._build_warnings(identifiers)

        domain_data = {
            "identifiers_hint": {
                "persistent_product_identifier": identifiers["persistent_product_identifier"],
                "persistent_product_identifier_scheme": identifiers["persistent_product_identifier_scheme"],
                "operator_identifier": identifiers["operator_identifier"],
                "facility_identifier": identifiers["facility_identifier"],
                "gtin_check_digit_verified": identifiers["gtin_check_digit_verified"],
            },
            "data_carrier_hint": {
                "resolver_url": identifiers["resolver_url"],
                "carrier_value": identifiers["carrier_value"],
                "is_persistent": identifiers["is_persistent"],
                "qr_ready": identifiers["qr_ready"],
            },
        }

        return {
            "success": True,
            "agent": self.AGENT_NAME,
            "data": {
                "product_group": group,
                "domain_data": domain_data,
                "assessment": {
                    "identifier_ready": len(gaps) == 0,
                    "qr_ready": identifiers["qr_ready"],
                    "resolver_ready": bool(identifiers["resolver_url"]),
                    "missing_fields": gaps,
                    "warnings": warnings,
                },
                "explanation": self._build_explanation(identifiers, gaps),
            },
            "errors": [],
            "warnings": warnings,
        }

    def _normalize_product_group(
        self,
        product_group: str | None,
        product_input: dict[str, Any] | None,
        reconciled_domain_data: dict[str, Any] | None,
    ) -> str:
        candidates = [
            product_group,
            (product_input or {}).get("product_group"),
            (product_input or {}).get("productGroup"),
            (reconciled_domain_data or {}).get("product_group"),
            (reconciled_domain_data or {}).get("productGroup"),
        ]

        espr_core = (reconciled_domain_data or {}).get("espr_core")
        if isinstance(espr_core, dict):
            candidates.extend(
                [
                    espr_core.get("product_group"),
                    espr_core.get("productGroup"),
                    espr_core.get("espr_category"),
                ]
            )

        for candidate in candidates:
            normalized = self._clean_string(candidate).lower()
            if normalized:
                return normalized

        return "unknown"

    def _build_source(
        self,
        *,
        product_input: dict[str, Any],
        reconciled_domain_data: dict[str, Any],
        public_package_url: str | None,
    ) -> dict[str, Any]:
        source = {}
        source.update(product_input)

        espr_core = reconciled_domain_data.get("espr_core")
        if isinstance(espr_core, dict):
            source.update(espr_core)

        source["public_package_url"] = public_package_url or source.get("public_package_url")
        return source

    def _extract_identifier_values(self, source: dict[str, Any]) -> dict[str, Any]:
        gtin = self._first_string(
            source,
            "gtin",
            "GTIN",
            "persistent_product_identifier",
            "persistentProductIdentifier",
            "product_identifier",
            "productIdentifier",
        )
        identifier_scheme = self._first_string(
            source,
            "persistent_product_identifier_scheme",
            "product_identifier_scheme",
            "identifier_scheme",
            "identifierScheme",
        )

        if gtin and self._looks_like_gtin(gtin):
            identifier_scheme = identifier_scheme or "GTIN"

        operator_identifier = self._first_string(
            source,
            "operator_identifier",
            "operatorIdentifier",
            "unique_operator_identifier",
            "uniqueOperatorIdentifier",
            "gln",
            "eori",
            "vat_number",
            "vatNumber",
        )

        facility_identifier = self._first_string(
            source,
            "facility_identifier",
            "facilityIdentifier",
            "unique_facility_identifier",
            "uniqueFacilityIdentifier",
            "facility_gln",
            "facilityGln",
        )

        resolver_url = self._first_string(
            source,
            "resolver_url",
            "resolverUrl",
            "public_package_url",
            "package_url",
            "passport_url",
            "passportUrl",
        )

        carrier_value = self._first_string(
            source,
            "carrier_value",
            "carrierValue",
            "qr_value",
            "qrValue",
            "data_carrier_value",
            "dataCarrierValue",
        ) or resolver_url

        is_persistent = self._is_persistent_url(resolver_url)
        gtin_check_digit_verified = (
            self._verify_gtin_check_digit(gtin) if gtin and self._looks_like_gtin(gtin) else False
        )

        return {
            "persistent_product_identifier": gtin,
            "persistent_product_identifier_scheme": identifier_scheme or ("GTIN" if gtin else ""),
            "operator_identifier": operator_identifier,
            "facility_identifier": facility_identifier,
            "resolver_url": resolver_url,
            "carrier_value": carrier_value,
            "is_persistent": is_persistent,
            "qr_ready": bool(carrier_value and resolver_url and is_persistent),
            "gtin_check_digit_verified": gtin_check_digit_verified,
        }

    def _build_identifier_gaps(
        self,
        identifiers: dict[str, Any],
        product_group: str,
    ) -> list[dict[str, Any]]:
        gaps: list[IdentifierCheck] = []
        regulatory_basis = self._regulatory_basis(product_group)

        if not identifiers["persistent_product_identifier"]:
            gaps.append(
                IdentifierCheck(
                    field=_REQUIRED_IDENTIFIER_FIELDS["persistent_product_identifier"],
                    severity="required",
                    blocking=True,
                    reason="No persistent product identifier is available.",
                    action=(
                        "Assign or provide a persistent product identifier from product "
                        "master data, such as GTIN, DID, or another controlled identifier."
                    ),
                    owner_hint="brand_owner",
                    regulatory_basis=regulatory_basis,
                )
            )
        elif identifiers["persistent_product_identifier_scheme"] == "GTIN" and not identifiers["gtin_check_digit_verified"]:
            gaps.append(
                IdentifierCheck(
                    field=_REQUIRED_IDENTIFIER_FIELDS["persistent_product_identifier"],
                    severity="required",
                    blocking=True,
                    reason="A GTIN-like identifier was provided but its check digit is invalid.",
                    action="Verify the GTIN against the GS1 source record or correct the identifier.",
                    owner_hint="brand_owner",
                    regulatory_basis=regulatory_basis,
                )
            )

        if not identifiers["operator_identifier"]:
            gaps.append(
                IdentifierCheck(
                    field=_REQUIRED_IDENTIFIER_FIELDS["operator_identifier"],
                    severity="recommended",
                    blocking=False,
                    reason="No responsible economic operator identifier is available.",
                    action="Provide GLN, EORI, VAT, LEI, or another controlled operator identifier.",
                    owner_hint="brand_owner",
                    regulatory_basis=regulatory_basis,
                )
            )

        if not identifiers["resolver_url"]:
            gaps.append(
                IdentifierCheck(
                    field=_REQUIRED_IDENTIFIER_FIELDS["resolver_url"],
                    severity="required",
                    blocking=True,
                    reason="No public resolver URL is available for the passport.",
                    action="Publish the passport package to a stable public location and assign the resolver URL.",
                    owner_hint="brand_owner",
                    regulatory_basis=None,
                )
            )

        if not identifiers["carrier_value"]:
            gaps.append(
                IdentifierCheck(
                    field=_REQUIRED_IDENTIFIER_FIELDS["carrier_value"],
                    severity="required",
                    blocking=True,
                    reason="No data-carrier value is available for QR/NFC resolution.",
                    action="Generate a data-carrier value after the public passport URL is known.",
                    owner_hint="brand_owner",
                    regulatory_basis=None,
                )
            )

        return [gap.as_gap() for gap in gaps]

    def _build_warnings(self, identifiers: dict[str, Any]) -> list[str]:
        warnings = []

        resolver_url = identifiers["resolver_url"]
        if resolver_url and not identifiers["is_persistent"]:
            warnings.append(
                "Resolver URL is present but is not persistent enough for print or packaging use."
            )

        if identifiers["carrier_value"] and not identifiers["qr_ready"]:
            warnings.append(
                "Data carrier value exists, but QR is not print-ready until a stable public resolver URL is assigned."
            )

        return warnings

    def _build_explanation(
        self,
        identifiers: dict[str, Any],
        gaps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if gaps:
            summary = (
                "Identifier and data-carrier readiness is incomplete. The passport should "
                "not be treated as packaging-ready until the listed identifier and resolver "
                "gaps are closed."
            )
        else:
            summary = (
                "Identifier and data-carrier readiness checks passed for the provided "
                "product, operator, and resolver data."
            )

        return {
            "summary": summary,
            "deterministic_checks": [
                "persistent product identifier presence",
                "GTIN check digit when identifier is GTIN-like",
                "operator identifier presence",
                "resolver URL presence",
                "data-carrier value presence",
                "QR readiness from persistent resolver URL",
            ],
            "llm_used": False,
            "qr_target_url": identifiers["resolver_url"],
        }

    def _fail_closed(self, *, product_group: str, reason: str) -> dict[str, Any]:
        return {
            "success": False,
            "agent": self.AGENT_NAME,
            "data": {
                "product_group": product_group,
                "domain_data": {},
                "assessment": {
                    "identifier_ready": False,
                    "qr_ready": False,
                    "resolver_ready": False,
                    "missing_fields": [],
                    "warnings": [reason],
                },
                "explanation": {
                    "summary": reason,
                    "llm_used": False,
                },
            },
            "errors": [reason],
            "warnings": [reason],
        }

    def _regulatory_basis(self, product_group: str) -> str | None:
        if product_group == "batteries":
            return "REG_2023_1542_BATTERIES"
        if product_group in {"textiles", "electrical_appliances"}:
            return "ESPR_2024_1781"
        return None

    def _first_string(self, data: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = self._clean_string(data.get(key))
            if value:
                return value
        return ""

    def _clean_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        return ""

    def _looks_like_gtin(self, value: str) -> bool:
        digits = "".join(char for char in value if char.isdigit())
        return len(digits) in {8, 12, 13, 14} and digits == value

    def _verify_gtin_check_digit(self, value: str) -> bool:
        digits = [int(char) for char in value if char.isdigit()]
        if len(digits) not in {8, 12, 13, 14}:
            return False

        check_digit = digits[-1]
        body = digits[:-1]
        total = 0

        for index, digit in enumerate(reversed(body), start=1):
            total += digit * (3 if index % 2 == 1 else 1)

        calculated = (10 - (total % 10)) % 10
        return calculated == check_digit

    def _is_persistent_url(self, value: str) -> bool:
        if not value:
            return False

        normalized = value.lower()
        if normalized.startswith("http://localhost") or normalized.startswith("https://localhost"):
            return False
        if normalized.startswith("file://"):
            return False
        if "127.0.0.1" in normalized:
            return False
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return True

        return False
