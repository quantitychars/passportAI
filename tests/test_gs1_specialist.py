from __future__ import annotations

from agents.gs1_specialist import GS1Specialist


def test_valid_battery_identifier_and_resolver_passes():
    result = GS1Specialist().run(
        product_group="batteries",
        product_input={
            "gtin": "12345678901231",
            "operator_identifier": "GLN:1234567890123",
            "facility_identifier": "FACILITY-001",
            "resolver_url": "https://passportai.example.com/passports/demo/passport.html",
        },
    )

    assert result["success"] is True
    assessment = result["data"]["assessment"]
    assert assessment["identifier_ready"] is True
    assert assessment["qr_ready"] is True
    assert assessment["resolver_ready"] is True
    assert assessment["missing_fields"] == []

    hints = result["data"]["domain_data"]
    assert hints["identifiers_hint"]["persistent_product_identifier"] == "12345678901231"
    assert hints["identifiers_hint"]["persistent_product_identifier_scheme"] == "GTIN"
    assert hints["identifiers_hint"]["gtin_check_digit_verified"] is True
    assert hints["data_carrier_hint"]["carrier_value"] == (
        "https://passportai.example.com/passports/demo/passport.html"
    )


def test_missing_required_identifier_and_resolver_fail_closed():
    result = GS1Specialist().run(
        product_group="batteries",
        product_input={"brand_name": "Demo Brand"},
    )

    assert result["success"] is True
    assessment = result["data"]["assessment"]
    assert assessment["identifier_ready"] is False
    assert assessment["qr_ready"] is False

    fields = {gap["field"] for gap in assessment["missing_fields"]}
    assert "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.value" in fields
    assert "dpp.regulatedCore.dataCarrier.resolverUrl" in fields
    assert "dpp.regulatedCore.dataCarrier.carrierValue" in fields

    blockers = [gap for gap in assessment["missing_fields"] if gap["blocking"]]
    assert blockers


def test_invalid_gtin_check_digit_is_blocking():
    result = GS1Specialist().run(
        product_group="batteries",
        product_input={
            "gtin": "12345678901234",
            "operator_identifier": "GLN:1234567890123",
            "resolver_url": "https://passportai.example.com/passports/demo/passport.html",
        },
    )

    gaps = result["data"]["assessment"]["missing_fields"]

    assert any(
        gap["field"] == "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.value"
        and "check digit is invalid" in gap["reason"]
        and gap["blocking"] is True
        for gap in gaps
    )


def test_localhost_resolver_warns_and_is_not_qr_ready():
    result = GS1Specialist().run(
        product_group="batteries",
        product_input={
            "gtin": "12345678901231",
            "operator_identifier": "GLN:1234567890123",
            "resolver_url": "http://localhost:8000/demo/passport.html",
        },
    )

    assessment = result["data"]["assessment"]

    assert assessment["resolver_ready"] is True
    assert assessment["qr_ready"] is False
    assert "not persistent enough" in result["warnings"][0]


def test_reconciled_domain_data_can_provide_identifier_context():
    result = GS1Specialist().run(
        reconciled_domain_data={
            "espr_core": {
                "product_group": "textiles",
                "gtin": "12345678901231",
                "operator_identifier": "GLN:1234567890123",
                "resolver_url": "https://passportai.example.com/passports/textile/passport.html",
            }
        }
    )

    assert result["success"] is True
    assert result["data"]["product_group"] == "textiles"
    assert result["data"]["assessment"]["identifier_ready"] is True


def test_unsupported_product_group_fails_closed():
    result = GS1Specialist().run(product_group="chemicals", product_input={})

    assert result["success"] is False
    assert result["data"]["assessment"]["identifier_ready"] is False
    assert result["data"]["assessment"]["qr_ready"] is False
    assert "Unsupported or unknown product group" in result["errors"][0]


def test_gs1_specialist_does_not_use_llm_for_identifier_checks():
    result = GS1Specialist().run(
        product_group="electrical_appliances",
        product_input={
            "gtin": "12345678901231",
            "operator_identifier": "GLN:1234567890123",
            "resolver_url": "https://passportai.example.com/passports/appliance/passport.html",
        },
    )

    assert result["data"]["explanation"]["llm_used"] is False
    assert any(
    "GTIN check digit" in check
    for check in result["data"]["explanation"]["deterministic_checks"]
)
