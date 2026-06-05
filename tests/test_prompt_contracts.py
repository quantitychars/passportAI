from __future__ import annotations

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"

EXPECTED_PROMPTS = {
    "data_audit.txt",
    "dpp_generation.txt",
    "gap_check.txt",
    "lca_assessment.txt",
    "lca_evidence_review.txt",
    "legal_evidence_review.txt",
    "legal_review.txt",
    "regulatory_classification.txt",
    "vision_analysis.txt",
}

PROMPTS_REQUIRING_CATEGORY_RULES = {
    "dpp_generation.txt",
    "gap_check.txt",
    "lca_assessment.txt",
    "lca_evidence_review.txt",
    "legal_evidence_review.txt",
    "legal_review.txt",
    "regulatory_classification.txt",
    "vision_analysis.txt",
}

EVIDENCE_SOURCE_VALUES = {
    "observed_from_image",
    "provided_by_user",
    "derived_from_evidence",
    "inferred_low_confidence",
    "missing",
}


def _prompt_text(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def test_expected_prompt_files_exist() -> None:
    existing = {path.name for path in PROMPT_DIR.glob("*.txt")}

    assert EXPECTED_PROMPTS <= existing


def test_prompts_require_structured_json_outputs() -> None:
    for prompt_name in EXPECTED_PROMPTS:
        text = _prompt_text(prompt_name).lower()

        assert "json" in text, prompt_name
        assert "return" in text and "only" in text, prompt_name


def test_prompts_forbid_inventing_product_facts() -> None:
    for prompt_name in EXPECTED_PROMPTS:
        text = _prompt_text(prompt_name).lower()

        assert "do not invent" in text, prompt_name
        assert "product facts" in text or "supplier" in text, prompt_name


def test_prompts_keep_missing_evidence_explicit() -> None:
    for prompt_name in EXPECTED_PROMPTS:
        text = _prompt_text(prompt_name).lower()

        assert "missing" in text, prompt_name
        assert "evidence" in text, prompt_name


def test_prompts_prohibit_unsupported_compliance_claims() -> None:
    for prompt_name in EXPECTED_PROMPTS:
        text = _prompt_text(prompt_name).lower()

        assert "unsupported" in text and "compliance" in text and "claim" in text, prompt_name


def test_prompts_use_evidence_source_vocabulary() -> None:
    for prompt_name in EXPECTED_PROMPTS:
        text = _prompt_text(prompt_name)

        for source_value in EVIDENCE_SOURCE_VALUES:
            assert source_value in text, f"{prompt_name} missing {source_value}"


def test_runtime_category_prompts_include_category_specific_rules() -> None:
    for prompt_name in PROMPTS_REQUIRING_CATEGORY_RULES:
        text = _prompt_text(prompt_name)

        assert "batteries" in text, prompt_name
        assert "electrical_appliances" in text, prompt_name
        assert "textiles" in text, prompt_name


def test_dpp_generation_prompt_is_schema_aware() -> None:
    text = _prompt_text("dpp_generation.txt")

    assert "schemas/universal_dpp.json" in text
    assert "schemas/battery_dpp.json" in text
    assert "schemas/electronics_dpp.json" in text
    assert "schemas/textile_dpp.json" in text
