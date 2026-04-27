from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict


class AuditAssessment(TypedDict, total=False):
    readiness_verdict: str
    readiness_score: int
    is_publishable: bool
    needs_human_review: bool
    missing_fields: list[dict[str, Any]]
    blocking_issues: list[str]


class DPPGenerator:
    """Projection-only Digital Product Passport generator.

    Responsibilities:
    - Accept already reconciled domain data from PassportPipeline
    - Accept audit policy from DataAuditAgent
    - Project only supported values into DPP schema structure
    - Never invent domain facts via free-form generation

    Non-responsibilities:
    - product classification
    - legal interpretation
    - GS1 truth
    - LCA calculation
    - multimodal synthesis
    - gap analysis

    Design invariants:
    - reconciled_domain_data is the only domain truth source
    - audit payload may affect publishability metadata, never product facts
    - exactly one sectoral DPP block must be projected
    - generator must be deterministic for the same normalized input
    - placeholders must be explicit system placeholders, never inferred facts
    """

    ISSUER_DID = "did:web:passportai.example.com"
    ISSUER_NAME = "PassportAI"
    SCHEMA_VERSION = "3.0.0"
    PASSPORT_VERSION = "1.0.0"
    GENERATOR_VERSION = "1.0.0"
    DPP_VALIDITY_YEARS = 10

    SUPPORTED_PRODUCT_GROUPS = {
        "textiles",
        "batteries",
        "electrical_appliances",
    }

    SECTOR_KEY_BY_GROUP = {
        "textiles": "sectoralTextile",
        "batteries": "sectoralBattery",
        "electrical_appliances": "sectoralElectricalAppliance",
    }

    DEFAULT_LEGAL_BASIS_BY_GROUP = {
        "textiles": ["ESPR_2024_1781"],
        "batteries": ["BATTERY_REG_2023_1542"],
        "electrical_appliances": ["ESPR_2024_1781"],
    }

    MANDATORY_UNDER_MAPPING = {
        "ESPR_2024_1781": "ESPR_2024_1781",
        "BATTERY_REG_2023_1542": "BATTERY_REG_2023_1542",
    }

    TEXTILE_COMPONENT_VALUES = {
        "body",
        "handle",
        "lining",
        "thread",
        "label",
        "print",
        "other",
    }

    TEXTILE_MANUFACTURING_STEP_VALUES = {
        "spinning",
        "weaving",
        "knitting",
        "dyeing",
        "printing",
        "cutting",
        "sewing",
        "finishing",
        "packing",
        "other",
    }

    # Draft-hostile schema placeholders.
    # These are explicit system placeholders, not model inventions.
    UNKNOWN_COUNTRY_CODE = "ZZ"
    UNKNOWN_CN_CODE = "0000"
    UNKNOWN_OPERATOR_NAME = "UNKNOWN_OPERATOR"
    UNKNOWN_PRODUCT_NAME = "UNKNOWN_PRODUCT"
    UNKNOWN_BATTERY_MODEL = "UNKNOWN_BATTERY_MODEL"
    UNKNOWN_MANUFACTURER_BATTERY_ID = "UNKNOWN_MANUFACTURER_BATTERY_ID"

    PENDING_OPERATOR_IDENTIFIER = "PENDING_OPERATOR_IDENTIFIER"
    PENDING_FACILITY_IDENTIFIER = "PENDING_FACILITY_IDENTIFIER"

    DEFAULT_SCHEMA_FILENAME = "universal_dpp.schema.json"

    def __init__(
    self,
    client: Any | None,
    prompts_dir: Path | None = None,
    schemas_dir: Path | None = None,
    jsonschema_module: Any | None = None,
    logger_: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.prompts_dir = prompts_dir or Path("prompts")
        self.schemas_dir = schemas_dir or Path("schemas")
        self.jsonschema_module = jsonschema_module
        self.logger = logger_ or logger
    # ------------------------------------------------------------------
    # New canonical entrypoint
    # ------------------------------------------------------------------

    def generate_from_reconciled_state(
        self,
        *,
        reconciled_domain_data: dict[str, Any],
        audit_payload: dict[str, Any] | None = None,
        passport_id: str | None = None,
        public_package_url: str | None = None,
        qr_url: str | None = None,
        human_review_status: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate a schema-shaped DPP VC from canonical pipeline state.

        Input contract:
        - reconciled_domain_data is the ONLY domain truth source
        - audit_payload supplies only quality/publishability policy

        This method does not accept raw vision/legal/regulatory outputs.
        """
        try:
            self._assert_reconciled_contract(reconciled_domain_data)
        except Exception:
            self.logger.exception("Invalid reconciled domain data contract for DPP generation")
            raise

        passport_id = passport_id or str(uuid.uuid4())
        audit_assessment = self._extract_audit_assessment(audit_payload)

        now = now or datetime.now(timezone.utc)
        valid_until = now + timedelta(days=365 * self.DPP_VALIDITY_YEARS)

        product_subject_id = self._build_product_subject_id(
            reconciled_domain_data=reconciled_domain_data,
            passport_id=passport_id,
        )

        dpp_document = self._build_dpp_document(
            reconciled_domain_data=reconciled_domain_data,
            audit_assessment=audit_assessment,
            passport_id=passport_id,
            product_subject_id=product_subject_id,
            now=now,
            valid_until=valid_until,
            public_package_url=public_package_url,
            qr_url=qr_url,
            human_review_status=human_review_status,
        )

        credential_subject = {
            "id": product_subject_id,
            "dpp": dpp_document,
        }

        return {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://schema.org",
                "https://ref.gs1.org/standards/gs1-jld/contexts/gs1-vocab.jsonld",
            ],
            "id": f"{self.ISSUER_DID}:passports:{passport_id}",
            "type": [
                "VerifiableCredential",
                "DigitalProductPassportCredential",
            ],
            "issuer": {
                "id": self.ISSUER_DID,
                "name": self.ISSUER_NAME,
            },
            "validFrom": self._isoformat(now),
            "validUntil": self._isoformat(valid_until),
            "credentialSubject": credential_subject,
        }

    # ------------------------------------------------------------------
    # Deprecated old entrypoints
    # ------------------------------------------------------------------

    def generate_from_text(self, description: str) -> dict[str, Any]:
        raise RuntimeError(
            "DPPGenerator.generate_from_text() is deprecated. "
            "Use generate_from_reconciled_state() from canonical pipeline state."
        )

    def generate_from_photo_and_text(
        self,
        image_path: str | Path,
        description: str,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "DPPGenerator.generate_from_photo_and_text() is deprecated. "
            "Use PassportPipeline + generate_from_reconciled_state()."
        )

    def merge_inputs(
        self,
        vision_output: dict[str, Any],
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError(
            "DPPGenerator.merge_inputs() is deprecated. "
            "Ownership-aware reconciliation belongs to PassportPipeline."
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, passport: dict[str, Any]) -> tuple[bool, list[str]]:
        """Light structural validation aligned to current projection contract."""
        errors: list[str] = []

        if not isinstance(passport, dict):
            return False, ["passport must be a dict"]

        required_top = [
            "@context",
            "id",
            "type",
            "issuer",
            "validFrom",
            "credentialSubject",
        ]
        for field in required_top:
            if field not in passport:
                errors.append(f"Missing required field: {field}")

        type_values = passport.get("type", [])
        if "VerifiableCredential" not in type_values:
            errors.append("type must include 'VerifiableCredential'")
        if "DigitalProductPassportCredential" not in type_values:
            errors.append("type must include 'DigitalProductPassportCredential'")

        credential_subject = passport.get("credentialSubject")
        if not isinstance(credential_subject, dict):
            errors.append("credentialSubject must be a dict")
            return len(errors) == 0, errors

        if "id" not in credential_subject:
            errors.append("credentialSubject.id is required")

        dpp = credential_subject.get("dpp")
        if not isinstance(dpp, dict):
            errors.append("credentialSubject.dpp must be a dict")
            return len(errors) == 0, errors

        if isinstance(dpp.get("dpp"), dict):
            errors.append(
                "credentialSubject.dpp must contain the DPP payload directly, "
                "not nested under credentialSubject.dpp.dpp"
            )
            return len(errors) == 0, errors

        product_group = dpp.get("productGroup")
        sector_keys = [
            key for key in self.SECTOR_KEY_BY_GROUP.values()
            if key in dpp
        ]
        if len(sector_keys) != 1:
            errors.append("Exactly one sectoral DPP block must be present")

        expected_sector_key = self.SECTOR_KEY_BY_GROUP.get(product_group)
        if expected_sector_key and sector_keys and sector_keys[0] != expected_sector_key:
            errors.append(
                f"productGroup '{product_group}' does not match sectoral block '{sector_keys[0]}'"
            )

        regulated_core = dpp.get("regulatedCore")
        if not isinstance(regulated_core, dict):
            errors.append("dpp.regulatedCore must be a dict")
        else:
            product_identity = regulated_core.get("productIdentity", {})
            if product_identity.get("esprCategory") != product_group:
                errors.append(
                    "regulatedCore.productIdentity.esprCategory must match productGroup"
                )

        return len(errors) == 0, errors

    def validate_with_jsonschema(
    self,
    passport: dict[str, Any],
    *,
    schema_name: str = DEFAULT_SCHEMA_FILENAME,
    ) -> tuple[bool, list[str]]:
        """Formal JSON Schema validation as a second validation layer."""
        if not isinstance(passport, dict):
            return False, ["passport must be a dict"]

        jsonschema = self.jsonschema_module
        if jsonschema is None:
            try:
                import jsonschema as imported_jsonschema  # type: ignore
                jsonschema = imported_jsonschema
            except Exception as exc:
                self.logger.warning("jsonschema dependency is unavailable: %s", exc)
                return False, [f"jsonschema dependency is unavailable: {exc}"]

        schema_path = self.schemas_dir / schema_name
        if not schema_path.exists():
            self.logger.error("JSON Schema file not found: %s", schema_path)
            return False, [f"JSON Schema file not found: {schema_path}"]

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.error("Failed to load JSON Schema '%s': %s", schema_path, exc)
            return False, [f"Failed to load JSON Schema '{schema_path}': {exc}"]

        try:
            validator = jsonschema.Draft202012Validator(schema)
            errors = sorted(validator.iter_errors(passport), key=lambda e: list(e.path))
        except Exception as exc:
            self.logger.exception("Failed to initialize or run JSON Schema validator")
            return False, [f"Failed to initialize JSON Schema validator: {exc}"]

        if not errors:
            return True, []

        rendered_errors: list[str] = []
        for error in errors:
            path = ".".join(str(part) for part in error.path)
            path_display = path or "<root>"
            rendered_errors.append(f"{path_display}: {error.message}")

        return False, rendered_errors

    # ------------------------------------------------------------------
    # Core builders
    # ------------------------------------------------------------------

    def _build_dpp_document(
        self,
        *,
        reconciled_domain_data: dict[str, Any],
        audit_assessment: AuditAssessment,
        passport_id: str,
        product_subject_id: str,
        now: datetime,
        valid_until: datetime,
        public_package_url: str | None,
        qr_url: str | None,
        human_review_status: str | None,
    ) -> dict[str, Any]:
        espr_core = reconciled_domain_data.get("espr_core", {})
        sectoral = reconciled_domain_data.get("sectoral", {})
        product_group = self._require_product_group(espr_core)
        sector_profile = self._build_sector_profile(espr_core)
        selected_sector_data = self._selected_sectoral_block(sectoral, product_group)

        readiness_verdict = audit_assessment.get("readiness_verdict")
        is_publishable = bool(audit_assessment.get("is_publishable", False))

        dpp_payload: dict[str, Any] = {
            "schemaVersion": self.SCHEMA_VERSION,
            "passportId": passport_id,
            "productGroup": product_group,
            "sectorProfile": sector_profile,
            "regulatedCore": self._build_regulated_core(
                espr_core=espr_core,
                product_group=product_group,
                passport_id=passport_id,
                product_subject_id=product_subject_id,
                now=now,
                valid_until=valid_until,
                public_package_url=public_package_url,
                qr_url=qr_url,
                readiness_verdict=readiness_verdict,
                is_publishable=is_publishable,
            ),
            "systemMetadata": self._build_system_metadata(
                now=now,
                reconciled_domain_data=reconciled_domain_data,
                audit_assessment=audit_assessment,
                human_review_status=human_review_status,
            ),
        }

        sector_key = self.SECTOR_KEY_BY_GROUP[product_group]
        if product_group == "textiles":
            dpp_payload[sector_key] = self._build_sectoral_textile(
                selected_sector_data,
                espr_core,
                now,
            )
        elif product_group == "batteries":
            dpp_payload[sector_key] = self._build_sectoral_battery(
                selected_sector_data,
                espr_core,
                now,
            )
        elif product_group == "electrical_appliances":
            dpp_payload[sector_key] = self._build_sectoral_electrical(
                selected_sector_data,
                espr_core,
            )

        voluntary_esg = reconciled_domain_data.get("voluntary_esg")
        if isinstance(voluntary_esg, dict):
            dpp_payload["voluntaryEsg"] = voluntary_esg

        return dpp_payload

    def _build_sector_profile(self, espr_core: dict[str, Any]) -> dict[str, Any]:
        source = espr_core.get("sector_profile", {}) or {}
        regulatory_source = source.get("regulatorySource") or source.get(
            "regulatory_source"
        )
        normalized_sources = self._dedupe_preserve_order(
            self._clean_list_of_str(regulatory_source)
        )
        version = self._normalize_semver(source.get("version") or "1.0.0")

        return {
            "name": self._non_empty_str(source.get("name")),
            "version": version,
            "regulatorySource": normalized_sources or ["SECTORAL_ACT_PENDING"],
        }

    def _build_regulated_core(
        self,
        *,
        espr_core: dict[str, Any],
        product_group: str,
        passport_id: str,
        product_subject_id: str,
        now: datetime,
        valid_until: datetime,
        public_package_url: str | None,
        qr_url: str | None,
        readiness_verdict: str | None,
        is_publishable: bool,
    ) -> dict[str, Any]:
        identifiers_hint = espr_core.get("identifiers_hint", {}) or {}
        data_carrier_hint = espr_core.get("data_carrier_hint", {}) or {}
        compliance_hint = espr_core.get("compliance_hint", {}) or {}
        operator_hint = espr_core.get("operator_hint", {}) or {}
        facility_hint = espr_core.get("facility_hint", {}) or {}
        registry_hint = espr_core.get("registry_hint", {}) or {}

        persistent_id_value = (
            self._non_empty_str(identifiers_hint.get("persistent_identifier_value"))
            or self._non_empty_str(identifiers_hint.get("gtin"))
            or f"{self.ISSUER_DID}:products:{passport_id}"
        )
        persistent_scheme = self._infer_product_identifier_scheme(persistent_id_value)

        operator_identifier_value = (
            self._non_empty_str(identifiers_hint.get("operator_identifier_value"))
            or self._non_empty_str(operator_hint.get("identifier"))
            or self.PENDING_OPERATOR_IDENTIFIER
        )
        operator_identifier_scheme = self._infer_operator_identifier_scheme(
            operator_identifier_value
        )

        facility_identifier_value = (
            self._non_empty_str(identifiers_hint.get("facility_identifier_value"))
            or self._non_empty_str(facility_hint.get("identifier"))
        )
        facility_identifier_scheme = self._infer_facility_identifier_scheme(
            facility_identifier_value
        )

        resolver_url = (
            self._non_empty_str(data_carrier_hint.get("resolver_url"))
            or self._non_empty_str(data_carrier_hint.get("public_resolver_url"))
            or self._non_empty_str(public_package_url)
            or self._non_empty_str(qr_url)
            or f"https://passportai.example.com/passports/{passport_id}"
        )

        status = "issued" if is_publishable else "draft"

        country_of_manufacture = self._country_or_unknown(
            espr_core.get("country_of_manufacture")
        )
        operator_country = self._country_or_unknown(
            operator_hint.get("country")
            or espr_core.get("country_of_origin")
            or espr_core.get("country_of_manufacture")
        )
        facility_country = self._country_or_null(
            facility_hint.get("country") or espr_core.get("country_of_manufacture")
        )

        legal_basis = self._normalized_legal_basis(
            espr_core.get("legal_basis"),
            product_group,
        )
        mandatory_under = self._mandatory_under_from_legal_basis(legal_basis)

        return {
            "passportIdentity": {
                "passportId": passport_id,
                "passportVersion": self.PASSPORT_VERSION,
                "status": status,
                "issuedAt": self._isoformat(now),
                "validFrom": self._isoformat(now),
                "validUntil": self._isoformat(valid_until),
                "passportApplicability": {
                    "isMandatoryUnderUnionLaw": bool(mandatory_under),
                    "mandatoryUnder": mandatory_under,
                    "applicabilityNotes": self._non_empty_str(
                        compliance_hint.get("applicability_notes")
                    ),
                },
            },
            "productIdentity": {
                "productId": product_subject_id,
                "productName": self._system_placeholder(
                    self._non_empty_str(espr_core.get("product_name")),
                    self.UNKNOWN_PRODUCT_NAME,
                ),
                "productDescription": self._non_empty_str(
                    espr_core.get("product_description")
                ),
                "brandName": self._non_empty_str(espr_core.get("brand_name")),
                "modelName": self._non_empty_str(espr_core.get("model_name")),
                "modelNumber": self._non_empty_str(espr_core.get("model_number")),
                "batchLot": self._non_empty_str(espr_core.get("batch_lot")),
                "serialNumber": self._non_empty_str(espr_core.get("serial_number")),
                "productImageUrl": self._non_empty_str(
                    espr_core.get("product_image_url")
                ),
                "esprCategory": self._non_empty_str(espr_core.get("espr_category"))
                or product_group,
                "cnCode": self._system_placeholder(
                    self._non_empty_str(espr_core.get("cn_code")),
                    self.UNKNOWN_CN_CODE,
                ),
                "granularityLevel": self._non_empty_str(
                    espr_core.get("granularity_level")
                )
                or "model",
                "eprelModelIdentifier": self._non_empty_str(
                    espr_core.get("eprel_model_identifier")
                ),
                "legalBasis": legal_basis,
            },
            "identifiers": {
                "persistentUniqueProductIdentifier": {
                    "value": str(persistent_id_value),
                    "scheme": persistent_scheme,
                    "format": self._non_empty_str(identifiers_hint.get("format")),
                    "issuingBody": self._non_empty_str(
                        identifiers_hint.get("issuing_body")
                    ),
                    "checkDigitVerified": bool(
                        identifiers_hint.get("check_digit_verified", False)
                    ),
                },
                "uniqueOperatorIdentifier": {
                    "value": str(operator_identifier_value),
                    "scheme": operator_identifier_scheme,
                    "issuingBody": self._non_empty_str(
                        operator_hint.get("issuing_body")
                    ),
                },
                "uniqueFacilityIdentifier": {
                    "value": self._system_placeholder(
                        facility_identifier_value,
                        self.PENDING_FACILITY_IDENTIFIER,
                    ),
                    "scheme": facility_identifier_scheme,
                    "issuingBody": self._non_empty_str(
                        facility_hint.get("issuing_body")
                    ),
                },
            },
            "dataCarrier": {
                "type": self._non_empty_str(data_carrier_hint.get("type")) or "QR",
                "carrierValue": self._non_empty_str(
                    data_carrier_hint.get("carrier_value")
                )
                or resolver_url,
                "resolverUrl": resolver_url,
                "physicalPlacement": self._non_empty_str(
                    data_carrier_hint.get("physical_placement")
                )
                or "digital_only",
                "standard": self._non_empty_str(data_carrier_hint.get("standard")),
                "isPersistent": bool(data_carrier_hint.get("is_persistent", True)),
            },
            "economicOperators": {
                "responsibleEconomicOperator": {
                    "role": self._non_empty_str(operator_hint.get("role"))
                    or "manufacturer",
                    "name": self._system_placeholder(
                        self._non_empty_str(operator_hint.get("name"))
                        or self._non_empty_str(espr_core.get("brand_name")),
                        self.UNKNOWN_OPERATOR_NAME,
                    ),
                    "identifierRef": str(operator_identifier_value),
                    "registrationNumber": self._non_empty_str(
                        operator_hint.get("registration_number")
                    ),
                    "vatNumber": self._non_empty_str(operator_hint.get("vat_number")),
                    "address": {
                        "streetAddress": self._non_empty_str(
                            operator_hint.get("street_address")
                        ),
                        "addressLocality": self._non_empty_str(
                            operator_hint.get("address_locality")
                        ),
                        "postalCode": self._non_empty_str(
                            operator_hint.get("postal_code")
                        ),
                        "addressCountry": self._country_or_null(
                            operator_hint.get("address_country")
                        ),
                    },
                    "country": operator_country,
                    "contactEmail": self._non_empty_str(
                        operator_hint.get("contact_email")
                    ),
                    "contactPhone": self._non_empty_str(
                        operator_hint.get("contact_phone")
                    ),
                    "website": self._non_empty_str(operator_hint.get("website")),
                }
            },
            "facilities": {
                "mainManufacturingFacility": {
                    "name": self._non_empty_str(facility_hint.get("name")),
                    "identifierRef": self._system_placeholder(
                        facility_identifier_value,
                        self.PENDING_FACILITY_IDENTIFIER,
                    ),
                    "address": {
                        "streetAddress": self._non_empty_str(
                            facility_hint.get("street_address")
                        ),
                        "addressLocality": self._non_empty_str(
                            facility_hint.get("address_locality")
                        ),
                        "postalCode": self._non_empty_str(
                            facility_hint.get("postal_code")
                        ),
                        "addressCountry": self._country_or_null(
                            facility_hint.get("address_country")
                        ),
                    },
                    "country": facility_country,
                    "facilityRole": self._non_empty_str(
                        facility_hint.get("facility_role")
                    ),
                }
            },
            "registry": {
                "registryStatus": self._non_empty_str(
                    registry_hint.get("registry_status")
                )
                or "pending",
                "registryRegistrationIdentifier": self._non_empty_str(
                    registry_hint.get("registration_identifier")
                ),
                "registeredAt": self._non_empty_str(registry_hint.get("registered_at")),
                "registryJurisdiction": "EU",
                "registryNotes": self._non_empty_str(
                    registry_hint.get("registry_notes")
                ),
            },
            "compliance": {
                "declarationOfConformity": {
                    "required": bool(
                        compliance_hint.get("declaration_required", False)
                    ),
                    "present": bool(compliance_hint.get("declaration_present", False)),
                    "documentUrl": self._non_empty_str(
                        compliance_hint.get("declaration_document_url")
                    ),
                    "documentReference": self._non_empty_str(
                        compliance_hint.get("declaration_reference")
                    ),
                },
                "technicalDocumentation": {
                    "present": bool(
                        compliance_hint.get("technical_documentation_present", False)
                    ),
                    "documentReference": self._non_empty_str(
                        compliance_hint.get("technical_documentation_reference")
                    ),
                    "documentUrl": self._non_empty_str(
                        compliance_hint.get("technical_documentation_url")
                    ),
                    "storageLocation": self._non_empty_str(
                        compliance_hint.get("technical_documentation_storage")
                    )
                    or "internal",
                    "lastUpdated": self._non_empty_str(
                        compliance_hint.get("technical_documentation_last_updated")
                    ),
                },
            },
            "accessControl": {
                "publicSections": [
                    "productIdentity",
                    "dataCarrier",
                    "passportIdentity",
                ],
                "restrictedSections": {
                    "marketSurveillanceAuthorities": [
                        "compliance",
                        "auditTrail",
                        "provenance",
                    ],
                    "customs": [
                        "productIdentity",
                        "identifiers",
                        "economicOperators",
                    ],
                    "economicOperators": [
                        "technicalDocumentation",
                        "qualityAssessment",
                    ],
                },
                "confidentialBusinessInformation": [],
            },
            "provenance": {
                "issuer": {
                    "name": self.ISSUER_NAME,
                    "did": self.ISSUER_DID,
                    "credentialReference": None,
                },
                "signedBy": {
                    "actor": None if not is_publishable else self.ISSUER_NAME,
                    "signatureReference": None,
                    "signatureType": None,
                },
                "lastVerifiedBy": None
                if readiness_verdict != "ready"
                else self.ISSUER_NAME,
                "lastVerifiedAt": None
                if readiness_verdict != "ready"
                else self._isoformat(now),
            },
            "auditTrail": {
                "createdAt": self._isoformat(now),
                "updatedAt": None,
                "changeLog": [
                    {
                        "timestamp": self._isoformat(now),
                        "actor": self.ISSUER_NAME,
                        "action": "create",
                        "section": "regulatedCore",
                        "reason": "Initial DPP projection from reconciled pipeline state",
                    }
                ],
            },
        }

    def _build_system_metadata(
        self,
        *,
        now: datetime,
        reconciled_domain_data: dict[str, Any],
        audit_assessment: AuditAssessment,
        human_review_status: str | None,
    ) -> dict[str, Any]:
        readiness_score = int(audit_assessment.get("readiness_score", 0))
        missing_fields = audit_assessment.get("missing_fields", []) or []
        needs_human_review = bool(audit_assessment.get("needs_human_review", False))
        is_publishable = bool(audit_assessment.get("is_publishable", False))

        projected_missing_fields = []
        for item in missing_fields:
            if not isinstance(item, dict):
                continue
            projected_missing_fields.append(
                {
                    "field": self._non_empty_str(item.get("field")),
                    "severity": self._non_empty_str(item.get("severity"))
                    or "required",
                    "action": self._non_empty_str(item.get("action")),
                    "regulatoryBasis": self._non_empty_str(
                        item.get("regulatory_basis")
                    ),
                    "deadline": self._non_empty_str(item.get("deadline")),
                }
            )

        breakdown = self._build_readiness_breakdown(
            projected_missing_fields,
            readiness_score,
        )
        attachments = self._build_attachments(reconciled_domain_data)

        review_status = human_review_status or self._derive_human_review_status(
            needs_human_review=needs_human_review,
            is_publishable=is_publishable,
        )

        # This hash is intentionally computed from reconciled domain data rather than
        # from the final VC envelope, so content drift can be detected independently
        # of transport-level metadata changes.
        dpp_payload_for_hash = {"dpp": reconciled_domain_data}
        content_hash = self._compute_content_hash(dpp_payload_for_hash)

        return {
            "platform": {
                "generatorName": self.ISSUER_NAME,
                "generatorVersion": self.GENERATOR_VERSION,
                "generationMethod": "hybrid",
                "humanReviewStatus": review_status,
            },
            "qualityAssessment": {
                "readinessScore": readiness_score,
                "readinessScoreBreakdown": breakdown,
                "missingFields": projected_missing_fields,
            },
            "technicalAssets": {
                "contentHash": f"sha256:{content_hash}",
                "attachments": attachments,
            },
            "derivationTrace": self._build_derivation_trace(reconciled_domain_data),
        }

    # ------------------------------------------------------------------
    # Sectoral builders
    # ------------------------------------------------------------------

    def _build_sectoral_textile(
        self,
        sector: dict[str, Any],
        espr_core: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        material_items = sector.get("material_composition") or []
        material_composition: list[dict[str, Any]] = []

        if material_items:
            for item in material_items:
                if not isinstance(item, dict):
                    continue
                material_composition.append(
                    {
                        "component": self._enum_or_default(
                            item.get("component"),
                            self.TEXTILE_COMPONENT_VALUES,
                            "other",
                        ),
                        "material": self._non_empty_str(item.get("material"))
                        or "unknown",
                        "percentage": float(item.get("percentage") or 0),
                        "recycledContentPercentage": item.get(
                            "recycled_content_percentage"
                        ),
                        "recycledContentType": self._non_empty_str(
                            item.get("recycled_content_type")
                        ),
                        "bioBased": bool(item.get("bio_based", False)),
                        "materialOriginCountry": self._country_or_null(
                            item.get("material_origin_country")
                        ),
                        "certifications": self._dedupe_preserve_order(
                            self._clean_list_of_str(item.get("certifications"))
                        ),
                    }
                )

        if material_composition:
            total_percentage = sum(
                item["percentage"] for item in material_composition
            )
            if total_percentage == 100:
                total_check = 100
            else:
                # Placeholders are explicit contract-preserving values.
                # They keep schema shape stable without pretending unknown facts are known.
                total_check = 100
                material_composition = [self._default_textile_composition_item()]
        else:
            material_composition = [self._default_textile_composition_item()]
            total_check = 100

        visible_certs = self._clean_list_of_str(
            espr_core.get("visible_certifications")
        )
        claims = sector.get("certifications") or []
        certification_names: list[str] = []

        for item in claims:
            if isinstance(item, dict):
                name = self._non_empty_str(item.get("name"))
                if name:
                    certification_names.append(name)

        certification_names.extend(visible_certs)
        certification_names = sorted(
            self._dedupe_preserve_order(certification_names)
        )

        return {
            "composition": {
                "materialComposition": material_composition,
                "totalPercentageCheck": total_check,
            },
            "substances": {
                "substancesOfConcernPresent": bool(
                    sector.get("substances_of_concern_present", False)
                ),
                "reachSvhcPresent": bool(sector.get("svhc_list")),
                "svhcCheckDate": self._date_only(now),
                "svhcList": [
                    {
                        "substanceName": self._non_empty_str(
                            item.get("substance_name")
                        )
                        or self._non_empty_str(item.get("name"))
                        or "unknown_substance",
                        "casNumber": self._non_empty_str(item.get("cas_number")),
                        "concentrationRange": self._non_empty_str(
                            item.get("concentration_range")
                        ),
                        "component": self._non_empty_str(item.get("component")),
                        "legalBasis": self._non_empty_str(item.get("legal_basis"))
                        or "REACH_SVHC",
                    }
                    for item in (sector.get("svhc_list") or [])
                    if isinstance(item, dict)
                ],
                "restrictedSubstancesNotes": None,
            },
            "manufacturing": {
                "countryOfManufacture": self._country_or_null(
                    sector.get("country_of_manufacture")
                    or espr_core.get("country_of_manufacture")
                ),
                "countryOfOrigin": self._country_or_null(
                    sector.get("country_of_origin")
                    or espr_core.get("country_of_origin")
                ),
                "yearOfManufacture": int(
                    sector.get("year_of_manufacture")
                    or espr_core.get("year_of_manufacture")
                    or now.year
                ),
                "manufacturingSteps": [
                    {
                        "step": self._enum_or_default(
                            item.get("step"),
                            self.TEXTILE_MANUFACTURING_STEP_VALUES,
                            "other",
                        ),
                        "country": self._country_or_null(item.get("country")),
                        "facilityRef": self._non_empty_str(item.get("facility_ref")),
                    }
                    for item in (sector.get("manufacturing_steps") or [])
                    if isinstance(item, dict)
                ],
            },
            "performanceAndDurability": {
                "durabilityYears": float(sector.get("durability_years") or 0),
                "durabilityBasis": self._non_empty_str(
                    sector.get("durability_basis")
                )
                or "estimated",
                "durabilityTestMethod": None,
                "washResistance": self._non_empty_str(
                    sector.get("wash_resistance")
                ),
                "abrasionResistance": self._non_empty_str(
                    sector.get("abrasion_resistance")
                ),
                "colourFastness": self._non_empty_str(
                    sector.get("colour_fastness")
                ),
                "pillingResistance": self._non_empty_str(
                    sector.get("pilling_resistance")
                ),
            },
            "repairAndMaintenance": {
                "repairabilityApplicable": bool(
                    sector.get("repairability_applicable", False)
                ),
                "repairabilityScore": sector.get("repairability_score"),
                "repairabilityMethod": None,
                "repairInstructionsUrl": self._non_empty_str(
                    sector.get("repair_instructions_url")
                ),
                "repairServiceAvailable": bool(
                    sector.get("repair_service_available", False)
                ),
                "repairContact": None,
                "sparePartsAvailabilityYears": None,
                "sparePartsNotes": None,
            },
            "careAndUse": {
                "userManualUrl": None,
                "careInstructionsText": self._non_empty_str(
                    sector.get("care_instructions_text")
                ),
                "careSymbolsStandard": "ISO_3758"
                if self._clean_list_of_str(sector.get("care_symbols"))
                else None,
                "careSymbols": self._dedupe_preserve_order(
                    self._clean_list_of_str(sector.get("care_symbols"))
                ),
                "warnings": self._dedupe_preserve_order(
                    self._clean_list_of_str(espr_core.get("visible_warnings"))
                ),
            },
            "endOfLife": {
                "reusable": bool(sector.get("reusable", False)),
                "recyclable": bool(sector.get("recyclable", False)),
                "recyclingInstructions": None,
                "industrialCompostable": False,
                "homeCompostable": False,
                "compostingInstructions": None,
                "takeBackAvailable": bool(
                    sector.get("take_back_available", False)
                ),
                "takeBackSchemeReference": None,
                "disassemblyRequired": bool(
                    sector.get("disassembly_required", False)
                ),
                "disassemblyInstructions": None,
                "sortingInformation": None,
            },
            "certificationAndClaims": {
                "certifications": [
                    {
                        "name": name,
                        "version": None,
                        "issuer": None,
                        "certificateNumber": None,
                        "validFrom": None,
                        "validUntil": None,
                        "documentUrl": None,
                        "scope": None,
                        "status": "unknown",
                    }
                    for name in certification_names
                ],
            },
        }

    def _build_sectoral_battery(
        self,
        sector: dict[str, Any],
        espr_core: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "batteryClassification": {
                "batteryCategory": self._non_empty_str(
                    sector.get("battery_category")
                )
                or "portable",
                "chemistry": self._non_empty_str(sector.get("chemistry")) or "other",
                "isRechargeable": bool(sector.get("is_rechargeable", False)),
                "passportRequired": bool(sector.get("passport_required", False)),
                "passportRequirementBasis": self._non_empty_str(
                    sector.get("passport_requirement_basis")
                ),
            },
            "batteryIdentity": {
                "batteryModelIdentifier": self._system_placeholder(
                    self._non_empty_str(sector.get("battery_model_identifier"))
                    or self._non_empty_str(espr_core.get("model_number")),
                    self.UNKNOWN_BATTERY_MODEL,
                ),
                "manufacturerBatteryIdentifier": self._system_placeholder(
                    self._non_empty_str(
                        sector.get("manufacturer_battery_identifier")
                    ),
                    self.UNKNOWN_MANUFACTURER_BATTERY_ID,
                ),
                "serialNumber": self._non_empty_str(sector.get("serial_number"))
                or self._non_empty_str(espr_core.get("serial_number")),
                "manufacturingDate": self._non_empty_str(
                    sector.get("manufacturing_date")
                )
                or self._date_only(now),
                "manufacturingPlace": self._non_empty_str(
                    sector.get("manufacturing_place")
                ),
            },
            "technicalCharacteristics": {
                "roundTripEnergyEfficiency": float(
                    sector.get("round_trip_energy_efficiency") or 0
                ),
                "expectedLifetime": {
                    "cycleLife": sector.get("cycle_life"),
                    "calendarLifeYears": sector.get("calendar_life_years"),
                },
                "operatingConditions": {
                    "ratedCapacityAh": sector.get("rated_capacity_ah"),
                    "nominalVoltageV": sector.get("nominal_voltage_v"),
                    "capacityKWh": sector.get("capacity_kwh"),
                },
            },
            "performanceAndDurability": {
                "stateOfHealth": {
                    "present": bool(sector.get("state_of_health_present", False)),
                    "value": sector.get("state_of_health_value"),
                    "measuredAt": self._non_empty_str(
                        sector.get("state_of_health_measured_at")
                    ),
                },
                "batteryManagementSystem": {
                    "present": bool(
                        sector.get("battery_management_system_present", False)
                    ),
                    "softwareVersion": self._non_empty_str(
                        sector.get("battery_management_system_version")
                    ),
                },
                "durabilityMetrics": {
                    "cycleLife": sector.get("cycle_life"),
                    "calendarLifeYears": sector.get("calendar_life_years"),
                },
            },
            "sustainabilityAndComposition": {
                "carbonFootprint": {
                    "declared": False,
                    "valueKgCo2e": None,
                    "methodology": None,
                },
                "criticalRawMaterials": sector.get("critical_raw_materials") or [],
                "hazardousSubstances": sector.get("hazardous_substances") or [],
                "recycledContent": {
                    "declared": False,
                    "overallPercentage": None,
                    "byMaterial": [],
                },
            },
            "conformityAndInformation": {
                "ceMarkingPresent": "CE" in self._clean_list_of_str(
                    espr_core.get("visible_markings")
                ),
                "declarationOfConformityReference": self._non_empty_str(
                    (espr_core.get("compliance_hint") or {}).get(
                        "declaration_reference"
                    )
                ),
                "labelInformation": {
                    "visibleWarnings": self._dedupe_preserve_order(
                        self._clean_list_of_str(espr_core.get("visible_warnings"))
                    ),
                    "visibleMarkings": self._dedupe_preserve_order(
                        self._clean_list_of_str(espr_core.get("visible_markings"))
                    ),
                },
            },
            "endOfLifeAndCircularity": {
                "removabilityAndReplaceability": {
                    "removable": sector.get("removable"),
                    "replaceable": sector.get("replaceable"),
                },
                "collectionAndTakeBack": {
                    "available": bool(sector.get("take_back_available", False)),
                    "schemeReference": self._non_empty_str(
                        sector.get("take_back_reference")
                    ),
                },
                "secondLifeStatus": self._non_empty_str(
                    sector.get("second_life_status")
                )
                or "unknown",
            },
        }

    def _build_sectoral_electrical(
        self,
        sector: dict[str, Any],
        espr_core: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "applianceClassification": {
                "applianceType": self._non_empty_str(
                    sector.get("appliance_type")
                )
                or "other",
                "energyRelatedProduct": bool(
                    sector.get("energy_related_product", False)
                ),
                "energyLabelRequired": sector.get("energy_label_required"),
                "eprelRegistered": sector.get("eprel_registered"),
            },
            "energyAndPerformance": {
                "energyEfficiency": {
                    "energyClass": self._non_empty_str(sector.get("energy_class")),
                    "energyConsumptionKWhPerYear": sector.get(
                        "energy_consumption_kwh_per_year"
                    ),
                    "energyConsumptionPerCycleKWh": sector.get(
                        "energy_consumption_per_cycle_kwh"
                    ),
                    "ecoProgrammeAvailable": sector.get("eco_programme_available"),
                    "testStandard": self._non_empty_str(
                        sector.get("test_standard")
                    ),
                },
                "waterConsumptionLitresPerCycle": sector.get(
                    "water_consumption_litres_per_cycle"
                ),
                "noiseEmissionDb": sector.get("noise_emission_db"),
                "performanceClaims": self._clean_list_of_str(
                    sector.get("performance_claims")
                ),
            },
            "repairAndService": {
                "repairabilityApplicable": bool(
                    sector.get("repairability_applicable", False)
                ),
                "repairabilityScore": sector.get("repairability_score"),
                "disassemblyMethod": self._non_empty_str(
                    sector.get("disassembly_method")
                ),
                "serviceInformationAvailable": bool(
                    sector.get("service_information_available", False)
                ),
                "repairInstructionsUrl": self._non_empty_str(
                    sector.get("repair_instructions_url")
                ),
                "spareParts": {
                    "available": bool(
                        (sector.get("spare_parts") or {}).get("available", False)
                    ),
                    "availabilityYears": (sector.get("spare_parts") or {}).get(
                        "availability_years"
                    ),
                    "orderReferenceUrl": self._non_empty_str(
                        (sector.get("spare_parts") or {}).get("order_reference_url")
                    ),
                    "professionalOnlyParts": self._clean_list_of_str(
                        (sector.get("spare_parts") or {}).get(
                            "professional_only_parts"
                        )
                    ),
                },
                "softwareSupportYears": sector.get("software_support_years"),
            },
            "materialsAndSubstances": {
                "materialCompositionSummary": self._non_empty_str(
                    sector.get("material_composition_summary")
                )
                or "unknown",
                "substancesOfConcern": sector.get("substances_of_concern") or [],
                "recycledContentPercentage": sector.get(
                    "recycled_content_percentage"
                ),
                "batteryIncluded": sector.get("battery_included"),
            },
            "documentationAndSoftware": {
                "userManualUrl": self._non_empty_str(
                    sector.get("user_manual_url")
                ),
                "technicalDocumentationReference": self._non_empty_str(
                    sector.get("technical_documentation_reference")
                ),
                "softwareUpdatePolicyUrl": self._non_empty_str(
                    sector.get("software_update_policy_url")
                ),
            },
            "endOfLife": {
                "recyclable": bool(sector.get("recyclable", False)),
                "wasteCollectionInformationAvailable": bool(
                    sector.get("waste_collection_information_available", False)
                ),
                "takeBackAvailable": sector.get("take_back_available"),
                "disposalInstructions": self._non_empty_str(
                    sector.get("disposal_instructions")
                ),
            },
        }

    # ------------------------------------------------------------------
    # Derivation trace
    # ------------------------------------------------------------------

    def _build_derivation_trace(
        self,
        reconciled_domain_data: dict[str, Any],
    ) -> list[dict[str, str]]:
        espr_core = reconciled_domain_data.get("espr_core", {}) or {}

        entries = [
            self._trace_entry(
                target_field="productGroup",
                source_path="espr_core.product_group",
                source_agent="RegulatoryConsultant",
                transformation="direct",
            ),
            self._trace_entry(
                target_field="sectorProfile.name",
                source_path="espr_core.sector_profile.name",
                source_agent="RegulatoryConsultant",
                transformation="direct",
            ),
            self._trace_entry(
                target_field="regulatedCore.productIdentity.esprCategory",
                source_path="espr_core.espr_category",
                source_agent="RegulatoryConsultant",
                transformation="direct",
            ),
            self._trace_entry(
                target_field="regulatedCore.identifiers.persistentUniqueProductIdentifier.value",
                source_path=(
                    "espr_core.identifiers_hint.persistent_identifier_value"
                    if self._non_empty_str(
                        (espr_core.get("identifiers_hint") or {}).get(
                            "persistent_identifier_value"
                        )
                    )
                    else "espr_core.identifiers_hint.gtin"
                ),
                source_agent="GS1Specialist",
                transformation="direct_or_fallback",
            ),
            self._trace_entry(
                target_field="regulatedCore.identifiers.uniqueOperatorIdentifier.value",
                source_path=(
                    "espr_core.identifiers_hint.operator_identifier_value"
                    if self._non_empty_str(
                        (espr_core.get("identifiers_hint") or {}).get(
                            "operator_identifier_value"
                        )
                    )
                    else "espr_core.operator_hint.identifier"
                ),
                source_agent="GS1Specialist",
                transformation="direct_or_placeholder",
            ),
            self._trace_entry(
                target_field="regulatedCore.dataCarrier.resolverUrl",
                source_path=(
                    "espr_core.data_carrier_hint.resolver_url"
                    if self._non_empty_str(
                        (espr_core.get("data_carrier_hint") or {}).get("resolver_url")
                    )
                    else "pipeline.public_package_url_or_qr_url"
                ),
                source_agent="GS1Specialist",
                transformation="direct_or_fallback",
            ),
            self._trace_entry(
                target_field="regulatedCore.compliance.declarationOfConformity.present",
                source_path="espr_core.compliance_hint.declaration_present",
                source_agent="LegalAgent",
                transformation="direct",
            ),
            self._trace_entry(
                target_field="regulatedCore.productIdentity.productName",
                source_path="espr_core.product_name",
                source_agent="VisionAgent",
                transformation="direct_or_placeholder",
            ),
        ]

        return entries

    def _trace_entry(
        self,
        *,
        target_field: str,
        source_path: str,
        source_agent: str,
        transformation: str,
    ) -> dict[str, str]:
        return {
            "targetField": target_field,
            "sourcePath": source_path,
            "sourceAgent": source_agent,
            "transformation": transformation,
        }

    # ------------------------------------------------------------------
    # Extraction / metadata helpers
    # ------------------------------------------------------------------

    def _extract_audit_assessment(
        self,
        audit_payload: dict[str, Any] | None,
    ) -> AuditAssessment:
        if not isinstance(audit_payload, dict):
            return {}

        if "assessment" in audit_payload and isinstance(
            audit_payload["assessment"], dict
        ):
            return audit_payload["assessment"]

        if audit_payload.get("success") is True:
            data = audit_payload.get("data")
            if isinstance(data, dict) and isinstance(data.get("assessment"), dict):
                return data["assessment"]

        return {}

    def _build_attachments(
        self,
        reconciled_domain_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        espr_core = reconciled_domain_data.get("espr_core", {}) or {}
        compliance_hint = espr_core.get("compliance_hint", {}) or {}

        attachments: list[dict[str, Any]] = []

        image_url = self._non_empty_str(espr_core.get("product_image_url"))
        if image_url:
            attachments.append(
                {
                    "name": "product_image",
                    "type": "image",
                    "url": image_url,
                    "hash": None,
                }
            )

        doc_url = self._non_empty_str(
            compliance_hint.get("declaration_document_url")
        )
        if doc_url:
            attachments.append(
                {
                    "name": "declaration_of_conformity",
                    "type": "document",
                    "url": doc_url,
                    "hash": None,
                }
            )

        return attachments

    def _build_readiness_breakdown(
        self,
        missing_fields: list[dict[str, Any]],
        readiness_score: int,
    ) -> dict[str, Any]:
        essential = sum(
            1 for item in missing_fields if item.get("severity") == "critical"
        )
        required = sum(
            1 for item in missing_fields if item.get("severity") == "required"
        )
        recommended = sum(
            1 for item in missing_fields if item.get("severity") == "recommended"
        )
        optional = sum(
            1 for item in missing_fields if item.get("severity") == "optional"
        )

        # Current schema expects this shape even though the real scoring logic lives in DataAuditAgent.
        return {
            "essentialFields": essential + required,
            "recommendedFields": recommended + optional,
            "documentsAttached": 0,
            "photoStandardized": 0,
            "total": readiness_score,
            "max": 100,
        }

    def _derive_human_review_status(
        self,
        *,
        needs_human_review: bool,
        is_publishable: bool,
    ) -> str:
        if is_publishable and not needs_human_review:
            return "approved"
        if needs_human_review:
            return "not_reviewed"
        return "reviewed"

    def _build_product_subject_id(
        self,
        *,
        reconciled_domain_data: dict[str, Any],
        passport_id: str,
    ) -> str:
        espr_core = reconciled_domain_data.get("espr_core", {}) or {}
        identifiers_hint = espr_core.get("identifiers_hint", {}) or {}

        preferred = (
            self._non_empty_str(identifiers_hint.get("persistent_identifier_value"))
            or self._non_empty_str(identifiers_hint.get("gtin"))
            or self._non_empty_str(espr_core.get("model_number"))
        )
        if preferred:
            return f"{self.ISSUER_DID}:products:{self._slug_fragment(preferred)}"
        return f"{self.ISSUER_DID}:products:{passport_id}"

    def _selected_sectoral_block(
        self,
        sectoral: dict[str, Any],
        product_group: str,
    ) -> dict[str, Any]:
        block = sectoral.get(product_group)
        return block if isinstance(block, dict) else {}

    # ------------------------------------------------------------------
    # Contract guards
    # ------------------------------------------------------------------

    def _assert_reconciled_contract(
        self,
        reconciled_domain_data: dict[str, Any],
    ) -> None:
        if not isinstance(reconciled_domain_data, dict):
            raise ValueError("reconciled_domain_data must be a dict")

        espr_core = reconciled_domain_data.get("espr_core")
        if not isinstance(espr_core, dict):
            raise ValueError("reconciled_domain_data.espr_core must be a dict")

        product_group = espr_core.get("product_group")
        if product_group not in self.SUPPORTED_PRODUCT_GROUPS:
            raise ValueError(
                "reconciled_domain_data.espr_core.product_group must be one of "
                f"{sorted(self.SUPPORTED_PRODUCT_GROUPS)}"
            )

        sectoral = reconciled_domain_data.get("sectoral")
        if not isinstance(sectoral, dict):
            raise ValueError("reconciled_domain_data.sectoral must be a dict")

        # We validate the product_group before any projection so that
        # downstream sector builders never need to defend against unknown sectors.
        filled = [
            key for key in self.SUPPORTED_PRODUCT_GROUPS
            if sectoral.get(key) is not None
        ]
        if len(filled) != 1:
            raise ValueError(
                "reconciled_domain_data.sectoral must contain exactly one non-null sectoral block"
            )

        if filled[0] != product_group:
            raise ValueError(
                "reconciled_domain_data.sectoral selected block must match espr_core.product_group"
            )

    # ------------------------------------------------------------------
    # Small normalization helpers
    # ------------------------------------------------------------------

    def _require_product_group(self, espr_core: dict[str, Any]) -> str:
        value = espr_core.get("product_group")
        if value not in self.SUPPORTED_PRODUCT_GROUPS:
            raise ValueError(
                "reconciled_domain_data.espr_core.product_group must be valid"
            )
        return value

    def _normalized_legal_basis(
        self,
        value: Any,
        product_group: str,
    ) -> list[str]:
        cleaned = self._clean_list_of_str(value)
        normalized = self._dedupe_preserve_order(cleaned)
        return normalized or self.DEFAULT_LEGAL_BASIS_BY_GROUP[product_group]

    def _mandatory_under_from_legal_basis(self, legal_basis: list[str]) -> list[str]:
        result = []
        for item in legal_basis:
            mapped = self.MANDATORY_UNDER_MAPPING.get(item)
            if mapped and mapped not in result:
                result.append(mapped)
        return result

    def _infer_product_identifier_scheme(self, value: Any) -> str:
        if not isinstance(value, str):
            return "OTHER"
        if value.startswith("did:"):
            return "DID"
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) == 14:
            return "GTIN"
        if len(digits) == 13:
            return "EAN"
        if len(digits) == 12:
            return "UPC"
        return "OTHER"

    def _infer_operator_identifier_scheme(self, value: Any) -> str:
        if not isinstance(value, str):
            return "OTHER"
        if value.startswith("GLN"):
            return "GLN"
        if value.startswith("LEI"):
            return "LEI"
        if value.startswith("VAT"):
            return "VAT"
        return "OTHER"

    def _infer_facility_identifier_scheme(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.startswith("GLN"):
            return "GLN"
        return "OTHER"

    def _normalize_semver(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            return "1.0.0"
        parts = value.strip().split(".")
        if len(parts) == 2:
            return f"{parts[0]}.{parts[1]}.0"
        if len(parts) == 1:
            return f"{parts[0]}.0.0"
        return value.strip()

    def _country_or_null(self, value: Any) -> str | None:
        text = self._non_empty_str(value)
        if text:
            text = text.upper()
            if len(text) == 2:
                return text
        return None

    def _country_or_unknown(self, value: Any) -> str:
        return self._country_or_null(value) or self.UNKNOWN_COUNTRY_CODE

    def _enum_or_default(self, value: Any, allowed: set[str], default: str) -> str:
        if isinstance(value, str) and value in allowed:
            return value
        return default

    def _date_only(self, value: datetime) -> str:
        return value.date().isoformat()

    def _isoformat(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    def _compute_content_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _non_empty_str(self, value: Any) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        return None

    def _clean_list_of_str(self, value: Any) -> list[str]:
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, tuple):
            raw_items = list(value)
        else:
            return []

        result: list[str] = []
        for item in raw_items:
            cleaned = self._non_empty_str(item)
            if cleaned:
                result.append(cleaned)
        return result

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            if item not in result:
                result.append(item)
        return result

    def _slug_fragment(self, value: Any) -> str:
        text = str(value).strip().lower()
        cleaned: list[str] = []
        for ch in text:
            if ch.isalnum():
                cleaned.append(ch)
            elif ch in {" ", "-", "_", "/", ":"}:
                cleaned.append("-")
        slug = "".join(cleaned).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug or "unknown-product"

    def _system_placeholder(self, value: Any, placeholder: str) -> Any:
        if value in (None, "", [], {}):
            return placeholder
        return value

    def _default_textile_composition_item(self) -> dict[str, Any]:
        return {
            "component": "other",
            "material": "unknown",
            "percentage": 100,
            "recycledContentPercentage": None,
            "recycledContentType": None,
            "bioBased": False,
            "materialOriginCountry": None,
            "certifications": [],
        }