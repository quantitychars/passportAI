"""Tests for DPPGenerator projection-only behavior.

These tests intentionally target the current architecture:
- PassportPipeline owns reconciliation.
- DPPGenerator consumes reconciled_domain_data + audit policy only.
- Deprecated generator-first entrypoints must stay blocked.
"""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.dpp_generator import DPPGenerator


@pytest.fixture
def generator() -> DPPGenerator:
    return DPPGenerator(client=None)


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 4, 27, 12, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def reconciled_textile_data() -> dict:
    return {
        "espr_core": {
            "product_group": "textiles",
            "espr_category": "textiles",
            "product_name": "Canvas Tote Bag",
            "product_description": "Reusable cotton canvas tote bag.",
            "brand_name": "PassportAI Demo",
            "model_name": "Demo Tote",
            "model_number": "TOTE-001",
            "country_of_manufacture": "UA",
            "legal_basis": ["ESPR_2024_1781"],
            "sector_profile": {
                "name": "textile_core_v1",
                "version": "1.0",
                "regulatory_source": ["ESPR_2024_1781"],
            },
            "identifiers_hint": {
                "gtin": "12345678901234",
                "operator_identifier_value": "GLN1234567890123",
            },
            "operator_hint": {
                "name": "Demo Manufacturer Ltd",
                "country": "UA",
            },
            "data_carrier_hint": {
                "type": "QR",
                "resolver_url": "https://example.test/passports/demo-passport",
            },
            "compliance_hint": {
                "declaration_present": True,
                "technical_documentation_present": True,
            },
        },
        "sectoral": {
            "textiles": {
                "material_composition": [
                    {
                        "component": "body",
                        "material": "cotton",
                        "percentage": 100,
                        "material_origin_country": "UA",
                    }
                ],
                "country_of_manufacture": "UA",
                "year_of_manufacture": 2026,
                "manufacturing_steps": [
                    {"step": "weaving", "country": "UA"},
                    {"step": "sewing", "country": "UA"},
                ],
                "reusable": True,
                "recyclable": True,
            },
            "batteries": None,
            "electrical_appliances": None,
        },
        "voluntary_esg": None,
    }


@pytest.fixture
def ready_audit_payload() -> dict:
    return {
        "assessment": {
            "readiness_verdict": "ready",
            "readiness_score": 96,
            "is_publishable": True,
            "needs_human_review": False,
            "missing_fields": [],
            "blocking_issues": [],
        }
    }


@pytest.fixture
def draft_audit_payload() -> dict:
    return {
        "assessment": {
            "readiness_verdict": "ready_with_gaps",
            "readiness_score": 61,
            "is_publishable": False,
            "needs_human_review": True,
            "missing_fields": [
                {
                    "field": "operator_identifier",
                    "severity": "required",
                    "reason": "Responsible operator identifier is not verified.",
                    "blocking": True,
                }
            ],
            "blocking_issues": ["Responsible operator identifier is not verified."],
        }
    }


def _generate(
    generator: DPPGenerator,
    reconciled_textile_data: dict,
    audit_payload: dict,
    fixed_now: datetime,
) -> dict:
    return generator.generate_from_reconciled_state(
        reconciled_domain_data=copy.deepcopy(reconciled_textile_data),
        audit_payload=copy.deepcopy(audit_payload),
        passport_id="demo-passport",
        public_package_url="https://example.test/passports/demo-passport/passport.json",
        qr_url="https://example.test/passports/demo-passport/qr.png",
        now=fixed_now,
    )


def _dpp_payload(passport: dict) -> dict:
    return passport["credentialSubject"]["dpp"]["dpp"]


class TestGenerateFromReconciledState:
    def test_generates_vc_from_reconciled_state(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        dpp = _dpp_payload(passport)

        assert passport["@context"][0] == "https://www.w3.org/ns/credentials/v2"
        assert passport["type"] == [
            "VerifiableCredential",
            "DigitalProductPassportCredential",
        ]
        assert passport["id"] == "did:web:passportai.example.com:passports:demo-passport"
        assert passport["validFrom"] == "2026-04-27T12:30:00Z"
        assert passport["validUntil"] == "2036-04-24T12:30:00Z"

        assert dpp["passportId"] == "demo-passport"
        assert dpp["productGroup"] == "textiles"
        assert "sectoralTextile" in dpp
        assert "sectoralBattery" not in dpp
        assert "sectoralElectricalAppliance" not in dpp

        product_identity = dpp["regulatedCore"]["productIdentity"]
        assert product_identity["productName"] == "Canvas Tote Bag"
        assert product_identity["brandName"] == "PassportAI Demo"
        assert product_identity["esprCategory"] == "textiles"

    def test_does_not_mutate_reconciled_input(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        before = copy.deepcopy(reconciled_textile_data)
        _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        assert reconciled_textile_data == before

    def test_rejects_invalid_reconciled_contract(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        broken = copy.deepcopy(reconciled_textile_data)
        broken["sectoral"]["batteries"] = {}

        with pytest.raises(ValueError, match="exactly one non-null sectoral block"):
            generator.generate_from_reconciled_state(
                reconciled_domain_data=broken,
                audit_payload=ready_audit_payload,
                passport_id="demo-passport",
                now=fixed_now,
            )


class TestDraftVsIssuedBehavior:
    def test_ready_publishable_audit_creates_issued_status(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        dpp = _dpp_payload(passport)

        assert dpp["regulatedCore"]["passportIdentity"]["status"] == "issued"
        assert dpp["systemMetadata"]["platform"]["humanReviewStatus"] == "approved"
        assert dpp["systemMetadata"]["qualityAssessment"]["readinessScore"] == 96

    def test_non_publishable_audit_creates_draft_status(
        self,
        generator,
        reconciled_textile_data,
        draft_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, draft_audit_payload, fixed_now)
        dpp = _dpp_payload(passport)

        assert dpp["regulatedCore"]["passportIdentity"]["status"] == "draft"
        assert dpp["systemMetadata"]["platform"]["humanReviewStatus"] == "not_reviewed"
        missing = dpp["systemMetadata"]["qualityAssessment"]["missingFields"]
        assert missing == [
            {
                "field": "operator_identifier",
                "severity": "required",
                "action": None,
                "regulatoryBasis": None,
                "deadline": None,
            }
        ]


class TestDerivationAndHash:
    def test_derivation_trace_is_present_and_agent_scoped(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        trace = _dpp_payload(passport)["systemMetadata"]["derivationTrace"]

        assert trace
        assert all(set(item) == {"targetField", "sourcePath", "sourceAgent", "transformation"} for item in trace)
        assert {item["sourceAgent"] for item in trace} >= {
            "RegulatoryConsultant",
            "GS1Specialist",
            "LegalAgent",
            "VisionAgent",
        }

    def test_content_hash_is_deterministic_and_key_order_independent(self, generator):
        payload_a = {"b": 2, "a": {"x": 1}}
        payload_b = {"a": {"x": 1}, "b": 2}

        assert generator._compute_content_hash(payload_a) == generator._compute_content_hash(payload_b)
        assert len(generator._compute_content_hash(payload_a)) == 64


class TestValidate:
    def test_valid_generated_passport_passes(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)

        valid, errors = generator.validate(passport)

        assert valid is True
        assert errors == []

    def test_missing_context_fails(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        del passport["@context"]

        valid, errors = generator.validate(passport)

        assert valid is False
        assert "Missing required field: @context" in errors

    def test_missing_credential_subject_fails(self, generator):
        valid, errors = generator.validate(
            {
                "@context": ["https://www.w3.org/ns/credentials/v2"],
                "id": "did:web:passportai.example.com:passports:x",
                "type": ["VerifiableCredential", "DigitalProductPassportCredential"],
                "issuer": {"id": "did:web:passportai.example.com"},
                "validFrom": "2026-04-27T00:00:00Z",
            }
        )

        assert valid is False
        assert "Missing required field: credentialSubject" in errors
        assert "credentialSubject must be a dict" in errors

    def test_sector_block_must_match_product_group(
        self,
        generator,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)
        dpp = _dpp_payload(passport)
        dpp["sectoralBattery"] = dpp.pop("sectoralTextile")

        valid, errors = generator.validate(passport)

        assert valid is False
        assert "Exactly one sectoral DPP block must be present" not in errors
        assert any("does not match sectoral block" in error for error in errors)


class TestValidateWithJsonschema:
    def test_validate_with_jsonschema_success(
        self,
        tmp_path,
        reconciled_textile_data,
        ready_audit_payload,
        fixed_now,
    ):
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        (schemas_dir / "universal_dpp.schema.json").write_text(
            """
            {
              "$schema": "https://json-schema.org/draft/2020-12/schema",
              "type": "object",
              "required": ["@context", "type", "credentialSubject"],
              "properties": {
                "@context": {"type": "array"},
                "type": {"type": "array", "contains": {"const": "VerifiableCredential"}},
                "credentialSubject": {"type": "object"}
              }
            }
            """,
            encoding="utf-8",
        )
        generator = DPPGenerator(client=None, schemas_dir=schemas_dir)
        passport = _generate(generator, reconciled_textile_data, ready_audit_payload, fixed_now)

        valid, errors = generator.validate_with_jsonschema(passport)

        assert valid is True
        assert errors == []

    def test_validate_with_jsonschema_reports_schema_errors(self, tmp_path):
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        (schemas_dir / "universal_dpp.schema.json").write_text(
            """
            {
              "$schema": "https://json-schema.org/draft/2020-12/schema",
              "type": "object",
              "required": ["credentialSubject"]
            }
            """,
            encoding="utf-8",
        )
        generator = DPPGenerator(client=None, schemas_dir=schemas_dir)

        valid, errors = generator.validate_with_jsonschema({"@context": []})

        assert valid is False
        assert any("credentialSubject" in error for error in errors)

    def test_validate_with_jsonschema_missing_schema_file_fails(self, tmp_path):
        generator = DPPGenerator(client=None, schemas_dir=tmp_path)

        valid, errors = generator.validate_with_jsonschema({})

        assert valid is False
        assert any("JSON Schema file not found" in error for error in errors)


class TestDeprecatedEntrypoints:
    def test_old_generator_first_entrypoints_remain_blocked(self, generator):
        with pytest.raises(RuntimeError, match="deprecated"):
            generator.generate_from_text("Cotton tote bag")

        with pytest.raises(RuntimeError, match="deprecated"):
            generator.generate_from_photo_and_text("image.png", "Cotton tote bag")

        with pytest.raises(RuntimeError, match="deprecated"):
            generator.merge_inputs({"category": "textiles"}, {"description": "bag"})
