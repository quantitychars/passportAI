from __future__ import annotations

from agents.lca_specialist import LCASpecialist


class FakeGemmaClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response or {}
        self.error = error
        self.calls = []

    def call_tool(self, prompt, tools, system_prompt=None):
        self.calls.append(
            {"prompt": prompt, "tools": tools, "system_prompt": system_prompt}
        )
        if self.error is not None:
            raise self.error
        return self.response


def test_battery_missing_sustainability_evidence_is_fail_closed():
    result = LCASpecialist(client=None).run(product_group="batteries")

    assert result["success"] is True
    payload = result["data"]

    fields = {item["field"]: item for item in payload["assessment"]["missing_fields"]}

    assert "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint" in fields
    assert "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials" in fields
    assert "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent" in fields
    assert fields[
        "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint"
    ]["blocking"] is True
    assert fields[
        "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint"
    ]["can_be_inferred"] is False
    assert payload["assessment"]["needs_human_review"] is True
    assert payload["domain_data"]["voluntary_esg"] is None


def test_supplier_evidence_references_close_battery_required_gaps():
    result = LCASpecialist(client=None).run(
        product_group="batteries",
        sustainability_evidence={
            "carbon_footprint_reference": "EPD-2026-001",
            "critical_raw_materials_reference": {"document_reference": "CRM-DECL-9"},
            "recycled_content_reference": {"url": "https://example.test/recycled.pdf"},
        },
    )

    assert result["success"] is True
    payload = result["data"]
    missing_fields = payload["assessment"]["missing_fields"]

    missing_paths = {item["field"] for item in missing_fields}
    assert "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint" not in missing_paths
    assert "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials" not in missing_paths
    assert "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent" not in missing_paths

    voluntary_esg = payload["domain_data"]["voluntary_esg"]
    assert voluntary_esg == {
        "evidenceReferences": {
            "carbon_footprint_reference": "EPD-2026-001",
            "critical_raw_materials_reference": {"document_reference": "CRM-DECL-9"},
            "recycled_content_reference": {"url": "https://example.test/recycled.pdf"},
        }
    }


def test_numeric_environmental_values_without_references_do_not_enter_domain_data():
    result = LCASpecialist(client=None).run(
        product_group="textiles",
        sustainability_evidence={
            "carbon_footprint_value": 12.4,
            "recycled_content_percentage": 30,
        },
    )

    assert result["success"] is True
    payload = result["data"]

    assert payload["domain_data"]["voluntary_esg"] is None
    warnings = "\n".join(payload["assessment"]["warnings"])
    assert "Numeric sustainability values" in warnings
    assert "carbon_footprint_value" in warnings
    assert "recycled_content_percentage" in warnings


def test_electrical_appliance_review_requests_bom_and_environmental_data():
    result = LCASpecialist(client=None).run(product_group="electrical_appliances")

    assert result["success"] is True
    fields = {item["field"] for item in result["data"]["assessment"]["missing_fields"]}

    assert "dpp.voluntaryEsg.footprint.carbonFootprint.gwpKgCo2e" in fields
    assert "dpp.sectoralElectricalAppliance.materialsAndSubstances.materialCompositionSummary" in fields


def test_unsupported_product_group_fails_closed():
    result = LCASpecialist(client=None).run(product_group="toys")

    assert result["success"] is False
    assert "Unsupported product_group" in result["error"]


def test_gemma_feedback_is_wording_only_and_preserves_missing_fields():
    fake_client = FakeGemmaClient(
        response={
            "agent_summary": "Ask the supplier for environmental proof before making sustainability claims.",
            "business_risks": [
                {
                    "title": "Unverified environmental claim",
                    "severity": "high",
                    "why_it_matters": "Unsupported claims can reduce trust.",
                }
            ],
            "recommended_next_actions": [
                {
                    "priority": "now",
                    "action": "Request supplier environmental documentation.",
                    "owner": "supplier",
                }
            ],
            "supplier_requests": [
                {
                    "request": "Provide EPD or sustainability dossier.",
                    "why_needed": "Needed to evidence environmental claims.",
                    "document_type": "environmental_declaration",
                }
            ],
            "where_to_get_data": [
                {
                    "missing_topic": "Carbon footprint",
                    "source": "supplier EPD",
                    "how_to_obtain": "Ask the manufacturer.",
                }
            ],
            # This must be ignored because the tool schema forbids it and the
            # sanitizer must not let advisory rewrite deterministic truth.
            "missing_fields": [],
        }
    )

    result = LCASpecialist(client=fake_client).run(
        product_group="batteries",
        use_gemma_feedback=True,
    )

    assert result["success"] is True
    payload = result["data"]
    assert fake_client.calls
    assert "Do not calculate carbon footprint values" in fake_client.calls[0]["system_prompt"]
    assert payload["advisory"]["agent_summary"].startswith("Ask the supplier")
    assert payload["assessment"]["missing_fields"]
    missing_paths = {item["field"] for item in payload["assessment"]["missing_fields"]}
    assert "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint" in missing_paths


def test_gemma_failure_preserves_deterministic_review():
    fake_client = FakeGemmaClient(error=RuntimeError("ollama unavailable"))

    result = LCASpecialist(client=fake_client).run(
        product_group="batteries",
        use_gemma_feedback=True,
    )

    assert result["success"] is True
    payload = result["data"]
    assert payload["assessment"]["missing_fields"]
    improvements = payload["advisory"]["next_batch_improvements"]
    assert any("Gemma sustainability feedback was unavailable" in item for item in improvements)
