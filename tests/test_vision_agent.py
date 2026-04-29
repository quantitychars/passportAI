import json
from pathlib import Path

import pytest

from agents.vision_agent import VisionAgent


class _FakeVisionClient:
    def __init__(self, response: str):
        self.response = response
        self.last_image_path = None
        self.last_prompt = None

    def analyze_image(self, image_path: Path, prompt: str) -> str:
        self.last_image_path = image_path
        self.last_prompt = prompt
        return self.response


def _run_with_response(tmp_path, response: str, *, product_group_hint="batteries"):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"fake-image")
    client = _FakeVisionClient(response)
    agent = VisionAgent(client=client)

    result = agent.run(
        image_url=str(image_path),
        description="Photo-only product evidence",
        product_group_hint=product_group_hint,
    )

    return result, client


def test_gemma_vision_uses_external_prompt_and_fake_client(tmp_path):
    response = json.dumps(
        {
            "category": "batteries",
            "materials": ["metal casing", "plastic sleeve"],
            "colors": ["black", "orange"],
            "dimensions_estimate": {"width_cm": None, "height_cm": None, "depth_cm": None},
            "certifications_visible": ["CE"],
            "special_markings": ["AA", "1.5V"],
            "product_type": "AA alkaline battery pack",
            "confidence": 0.86,
            # Adversarial fields must not enter product truth.
            "brand_name": "Invented Brand",
            "supplier": "Invented Supplier",
            "country_of_origin": "DE",
            "model_number": "MODEL-123",
        }
    )

    result, client = _run_with_response(tmp_path, response)

    assert result["success"] is True
    assert result["is_mock"] is False
    assert client.last_image_path is not None
    assert "Allowed category values" in client.last_prompt
    assert "Do not invent supplier" in client.last_prompt

    payload = result["data"]
    espr_core = payload["domain_data"]["espr_core"]

    assert espr_core["product_group_hint"] == "batteries"
    assert espr_core["product_name"] == "AA alkaline battery pack"
    assert espr_core["product_image_url"].endswith("product.jpg")
    assert espr_core["brand_name"] is None
    assert espr_core["model_name"] is None
    assert espr_core["model_number"] is None
    assert espr_core["serial_number"] is None
    assert espr_core["batch_lot"] is None
    assert "AA" in espr_core["visible_markings"]
    assert "CE" in espr_core["visible_certifications"]
    assert payload["domain_data"]["sectoral"]["batteries"]["chemistry"] is None
    assert payload["assessment"]["needs_human_review"] is True


def test_gemma_invalid_json_fails_closed(tmp_path):
    result, _client = _run_with_response(
        tmp_path,
        "this is not json",
    )

    assert result["success"] is False
    assert result["agent"] == "VisionAgent"
    assert "Expecting value" in result["error"] or "Gemma vision response" in result["error"]


def test_gemma_unknown_category_returns_insufficient_payload(tmp_path):
    response = json.dumps(
        {
            "category": "unknown",
            "materials": [],
            "colors": [],
            "dimensions_estimate": {"width_cm": None, "height_cm": None, "depth_cm": None},
            "certifications_visible": [],
            "special_markings": [],
            "product_type": "unclear object",
            "confidence": 0.22,
        }
    )

    result, _client = _run_with_response(tmp_path, response, product_group_hint="textiles")

    assert result["success"] is True
    payload = result["data"]
    espr_core = payload["domain_data"]["espr_core"]

    assert espr_core["product_group_hint"] is None
    assert espr_core["product_name"] is None
    assert payload["assessment"]["confidence_source"] == "insufficient_data"
    assert payload["assessment"]["needs_human_review"] is True
    assert any(
        "supported product group" in warning
        for warning in payload["assessment"]["warnings"]
    )


def test_gemma_supported_category_alias_normalizes_electronics(tmp_path):
    response = json.dumps(
        {
            "category": "electronics",
            "materials": ["plastic"],
            "colors": ["white"],
            "dimensions_estimate": {"width_cm": None, "height_cm": None, "depth_cm": None},
            "certifications_visible": [],
            "special_markings": ["energy label"],
            "product_type": "compact electrical appliance",
            "confidence": 0.74,
        }
    )

    result, _client = _run_with_response(
        tmp_path,
        response,
        product_group_hint="electrical_appliances",
    )

    assert result["success"] is True
    espr_core = result["data"]["domain_data"]["espr_core"]
    assert espr_core["product_group_hint"] == "electrical_appliances"
    assert result["data"]["domain_data"]["sectoral"]["electrical_appliances"]["appliance_type"] == "compact electrical appliance"
