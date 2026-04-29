from __future__ import annotations

import json

import pytest

from agents.regulatory_consultant import RegulatoryConsultant


class FakeGemmaClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.temperatures: list[float] = []

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        self.prompts.append(prompt)
        self.temperatures.append(temperature)
        return self.response


def _payload(result: dict):
    assert result["success"] is True, result
    return result["data"]


@pytest.mark.parametrize(
    ("input_group", "expected_group", "expected_profile"),
    [
        ("textiles", "textiles", "textile_core_v1"),
        ("batteries", "batteries", "battery_passport_annex_xiii_v1"),
        ("electrical_appliances", "electrical_appliances", "electrical_appliance_espr_ready_v1"),
        ("battery_pack", "batteries", "battery_passport_annex_xiii_v1"),
        ("electronics", "electrical_appliances", "electrical_appliance_espr_ready_v1"),
    ],
)
def test_deterministic_classification_supported_groups(input_group, expected_group, expected_profile):
    result = RegulatoryConsultant(client=None).run(product_group=input_group)
    payload = _payload(result)

    assert result["is_mock"] is False
    espr_core = payload["domain_data"]["espr_core"]
    assert espr_core["product_group"] == expected_group
    assert espr_core["espr_category"] == expected_group
    assert espr_core["sector_profile"]["name"] == expected_profile
    assert payload["assessment"]["classification"]["gemma_used_for_classification"] is False
    assert payload["advisory"]["agent_summary"]
    assert payload["assessment"]["missing_fields"]


def test_unsupported_category_fails_closed():
    result = RegulatoryConsultant(client=None).run(product_group="cosmetics")

    assert result["success"] is False
    assert "Unsupported product_group" in result["error"]


def test_gemma_explanation_is_optional_and_absent_without_client():
    result = RegulatoryConsultant(client=None, use_gemma_explanation=True).run(
        product_group="batteries",
        product_description="Industrial battery module",
    )
    payload = _payload(result)

    assert "gemma_explanation" not in payload["advisory"]
    assert payload["domain_data"]["espr_core"]["product_group"] == "batteries"


def test_gemma_explanation_adds_wording_without_changing_domain_truth():
    fake = FakeGemmaClient(
        json.dumps(
            {
                "user_explanation": "This is treated as a battery passport workflow because the deterministic category is batteries.",
                "classification_uncertainty": "Supplier confirmation is still required for battery category and chemistry.",
                "required_evidence_hints": [
                    "Ask the supplier for battery category evidence.",
                    "Ask the supplier for battery chemistry evidence.",
                ],
                "next_questions": ["Is this portable, industrial, EV, LMT, or SLI?"],
                "product_group": "textiles",
            }
        )
    )

    result = RegulatoryConsultant(
        client=fake,
        use_gemma_explanation=True,
    ).run(
        product_group="batteries",
        product_description="Photo-only battery product",
        vision_result={"domain_data": {"espr_core": {"product_group_hint": "batteries"}}},
    )
    payload = _payload(result)

    assert payload["domain_data"]["espr_core"]["product_group"] == "batteries"
    assert payload["domain_data"]["espr_core"]["sector_profile"]["name"] == "battery_passport_annex_xiii_v1"
    assert payload["advisory"]["gemma_explanation"]["source"] == "gemma_wording_only"
    assert "battery passport workflow" in payload["advisory"]["gemma_explanation"]["user_explanation"]
    assert fake.temperatures == [0.1]
    assert "DETERMINISTIC CONTEXT JSON" in fake.prompts[0]
    assert "Do not change product_group" in fake.prompts[0]


def test_invalid_gemma_explanation_falls_back_without_failing_classification():
    fake = FakeGemmaClient("not json")

    result = RegulatoryConsultant(
        client=fake,
        use_gemma_explanation=True,
    ).run(product_group="textiles")
    payload = _payload(result)

    assert payload["domain_data"]["espr_core"]["product_group"] == "textiles"
    explanation = payload["advisory"]["gemma_explanation"]
    assert explanation["source"] == "deterministic_fallback"
    assert "Gemma explanation failed" in " ".join(payload["assessment"]["warnings"])


def test_gemma_explanation_is_bounded_to_allowed_keys():
    fake = FakeGemmaClient(
        json.dumps(
            {
                "user_explanation": "x" * 2000,
                "classification_uncertainty": "y" * 2000,
                "required_evidence_hints": ["hint" + str(i) for i in range(20)],
                "next_questions": ["question" + str(i) for i in range(20)],
                "new_product_fact": "do not keep this",
            }
        )
    )

    payload = _payload(
        RegulatoryConsultant(client=fake, use_gemma_explanation=True).run(
            product_group="electrical_appliances"
        )
    )
    explanation = payload["advisory"]["gemma_explanation"]

    assert set(explanation) == {
        "user_explanation",
        "classification_uncertainty",
        "required_evidence_hints",
        "next_questions",
        "source",
    }
    assert len(explanation["user_explanation"]) == 900
    assert len(explanation["classification_uncertainty"]) == 600
    assert len(explanation["required_evidence_hints"]) == 8
    assert len(explanation["next_questions"]) == 6
