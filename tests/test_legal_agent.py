from __future__ import annotations

from agents.legal_agent import LegalAgent
from agents.validation import validate_agent_output


class FakeGemmaClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call_tool(self, prompt, tools, system_prompt=None):
        self.calls.append({"prompt": prompt, "tools": tools, "system_prompt": system_prompt})
        return self.response


def _payload(result):
    assert result["success"] is True
    return result["data"]


def _missing_fields(payload):
    return payload["assessment"]["missing_fields"]


def test_battery_missing_legal_evidence_is_fail_closed():
    result = LegalAgent(client=None).run(product_group="batteries")
    payload = _payload(result)

    assert result["is_mock"] is False
    assert payload["domain_data"]["espr_core"]["compliance_hint"]["declaration_of_conformity"]["present"] is False
    assert payload["assessment"]["needs_human_review"] is True

    fields = {item["field"]: item for item in _missing_fields(payload)}
    assert "dpp.regulatedCore.compliance.declarationOfConformity" in fields
    assert fields["dpp.regulatedCore.compliance.declarationOfConformity"]["severity"] == "critical"
    assert "dpp.regulatedCore.compliance.technicalDocumentation" in fields
    assert "dpp.sectoralBattery.conformityAndInformation.declarationOfConformityReference" in fields

    errors = validate_agent_output("LegalAgent", payload)
    assert errors == []


def test_supplied_battery_documents_close_core_legal_gaps():
    result = LegalAgent(client=None).run(
        product_group="batteries",
        evidence_refs={
            "declaration_of_conformity_reference": "DOC-2026-001",
            "technical_documentation_reference": "TECH-FILE-2026-001",
            "battery_declaration_of_conformity_reference": "BATTERY-DOC-2026-001",
        },
    )
    payload = _payload(result)

    assert payload["domain_data"]["espr_core"]["compliance_hint"]["declaration_of_conformity"]["present"] is True
    assert payload["domain_data"]["espr_core"]["compliance_hint"]["technical_documentation"]["present"] is True
    assert _missing_fields(payload) == []
    assert payload["assessment"]["needs_human_review"] is False


def test_electrical_appliance_requires_rohs_evidence():
    result = LegalAgent(client=None).run(product_group="electrical_appliances")
    payload = _payload(result)

    fields = {item["field"] for item in _missing_fields(payload)}
    assert "dpp.regulatedCore.compliance.declarationOfConformity" in fields
    assert "dpp.regulatedCore.compliance.technicalDocumentation" in fields
    assert "dpp.sectoralElectricalAppliance.compliance.rohsDeclarationReference" in fields

    rohs_gap = next(
        item for item in _missing_fields(payload)
        if item["field"] == "dpp.sectoralElectricalAppliance.compliance.rohsDeclarationReference"
    )
    assert rohs_gap["source_domain"] == "legal"
    assert rohs_gap["can_be_inferred"] is False


def test_textile_visible_claims_require_certificate_evidence():
    result = LegalAgent(client=None).run(
        product_group="textiles",
        visible_claims=["organic", "OEKO-TEX"],
    )
    payload = _payload(result)

    fields = {item["field"] for item in _missing_fields(payload)}
    assert "dpp.sectoralTextile.certificationAndClaims.certifications" in fields
    assert "dpp.sectoralTextile.substances" in fields


def test_unsupported_product_group_fails_closed():
    result = LegalAgent(client=None).run(product_group="furniture")

    assert result["success"] is False
    assert "Unsupported product_group" in result["error"]


def test_gemma_feedback_is_bounded_and_cannot_change_legal_facts():
    fake = FakeGemmaClient(
        {
            "summary": "Ask the supplier for declaration and technical evidence.",
            "why_it_matters": "The passport must not imply conformity without documents.",
            "next_steps": [
                "Request Declaration of Conformity.",
                "Request technical documentation reference.",
            ],
            "readiness_score": 100,
            "new_fact": "This must be ignored.",
        }
    )

    result = LegalAgent(client=fake, use_gemma_feedback=True).run(product_group="batteries")
    payload = _payload(result)

    assert len(fake.calls) == 1
    assert len(_missing_fields(payload)) == 3
    assert payload["assessment"]["needs_human_review"] is True

    feedback = payload["advisory"]["legal_feedback"]
    assert feedback == {
        "source": "gemma_wording",
        "summary": "Ask the supplier for declaration and technical evidence.",
        "why_it_matters": "The passport must not imply conformity without documents.",
        "next_steps": [
            "Request Declaration of Conformity.",
            "Request technical documentation reference.",
        ],
    }
    assert "readiness_score" not in feedback
    assert "new_fact" not in feedback


def test_gemma_feedback_failure_preserves_deterministic_review():
    class FailingClient:
        def call_tool(self, *args, **kwargs):
            raise RuntimeError("ollama unavailable")

    result = LegalAgent(client=FailingClient(), use_gemma_feedback=True).run(
        product_group="batteries"
    )
    payload = _payload(result)

    assert len(_missing_fields(payload)) == 3
    assert payload["advisory"]["legal_feedback"]["source"] == "deterministic_fallback"
    assert "ollama unavailable" in payload["advisory"]["legal_feedback"]["why_it_matters"]
