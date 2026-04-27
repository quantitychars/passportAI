from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.gap_report import GapReportGenerator


@pytest.fixture
def audit_result() -> dict:
    return {
        "success": True,
        "agent": "DataAuditAgent",
        "data": {
            "domain_data": {
                "espr_core": {
                    "product_name": "Canvas Tote Bag",
                    "brand_name": "Demo Brand",
                    "model_name": "TOTE-001",
                    "product_group": "textiles",
                    "espr_category": "textiles",
                    "sector_profile": {"name": "textile_core_v1"},
                }
            },
            "assessment": {
                "readiness_score": 42,
                "readiness_verdict": "not_ready",
                "is_publishable": False,
                "needs_human_review": True,
                "blocking_issues": ["Missing stable product identifier."],
                "contradictions": ["Visual textile hint conflicts with regulatory category."],
                "warnings": ["Photo evidence is incomplete."],
                "assumptions": ["No new product facts were created."],
                "missing_fields": [
                    {
                        "gap_id": "operator_identifier:missing",
                        "field": "operator_identifier",
                        "severity": "critical",
                        "blocking": True,
                        "reason_code": "missing",
                        "reason": "No operator identifier was provided.",
                        "why_it_matters": "Needed for accountable traceability.",
                        "current_evidence_status": "absent",
                        "acceptable_evidence": ["system_export", "document"],
                        "where_to_get_data": "ERP or GS1 registry",
                        "closure_condition": "Provide a verified operator identifier.",
                        "action": "Add the operator identifier from product master data.",
                        "owner_hint": "brand_owner",
                        "source_agents": ["GS1Specialist"],
                        "requires_supplier_confirmation": False,
                    },
                    {
                        "gap_id": "fiber_composition:photo_insufficient",
                        "field": "fiber_composition",
                        "severity": "required",
                        "blocking": False,
                        "reason_code": "photo_insufficient",
                        "reason": "Label was not visible in the photo.",
                        "why_it_matters": "Textile composition should not be inferred from a weak image.",
                        "current_evidence_status": "photo_only",
                        "acceptable_evidence": ["label_photo", "supplier_statement"],
                        "where_to_get_data": "label close-up or supplier specification",
                        "closure_condition": "Provide visible label evidence or supplier statement.",
                        "action": "Upload a close-up of the textile label.",
                        "owner_hint": "manufacturer",
                        "source_agents": ["VisionAgent"],
                        "requires_supplier_confirmation": True,
                    },
                    {
                        "gap_id": "declaration_of_conformity:unverified",
                        "field": "declaration_of_conformity",
                        "severity": "required",
                        "blocking": False,
                        "reason_code": "unverified",
                        "reason": "Document reference exists but has not been verified.",
                        "why_it_matters": "Legal evidence must be defensible.",
                        "current_evidence_status": "document_present_unverified",
                        "acceptable_evidence": ["document"],
                        "where_to_get_data": "technical documentation file",
                        "closure_condition": "Attach or verify the declaration document.",
                        "action": "Verify declaration of conformity reference.",
                        "owner_hint": "internal_compliance",
                        "source_agents": ["LegalAgent"],
                        "requires_supplier_confirmation": False,
                    },
                ],
            },
            "advisory": {
                "agent_summary": "Audit found blocking traceability gaps and weak textile evidence.",
                "business_risks": ["Publishing now could expose unsupported compliance claims."],
                "recommended_next_actions": [
                    {
                        "priority": "now",
                        "owner": "brand_owner",
                        "action": "Resolve missing identifier before publication.",
                    },
                    {
                        "priority": "soon",
                        "owner": "manufacturer",
                        "action": "Collect label close-up for fiber composition.",
                    },
                ],
                "supplier_requests": [
                    {
                        "request": "Provide fiber composition statement.",
                        "why_needed": "Closes weak textile evidence.",
                        "document_type": "supplier statement",
                    }
                ],
                "where_to_get_data": [
                    {
                        "missing_topic": "operator_identifier",
                        "source": "ERP or GS1 registry",
                        "how_to_obtain": "Export identifier from product master data.",
                    }
                ],
            },
        },
    }


def test_generate_writes_human_readable_html(tmp_path, audit_result):
    generator = GapReportGenerator(client=None)
    fixed_now = datetime(2026, 4, 27, 13, 0, tzinfo=timezone.utc)

    report_path = generator.generate(
        audit_result=audit_result,
        output_dir=tmp_path,
        passport_id="demo-passport",
        generated_at=fixed_now,
    )

    assert report_path == tmp_path / "gap_report.html"
    html = report_path.read_text(encoding="utf-8")

    assert "Canvas Tote Bag" in html
    assert "Publication is blocked" in html
    assert "operator_identifier" in html
    assert "fiber_composition" in html
    assert "declaration_of_conformity" in html
    assert "ERP or GS1 registry" in html
    assert "Supplier request pack" in html
    assert "2026-04-27T13:00:00Z" in html
    assert "DPP JSON used as source = False" in html


def test_build_view_model_groups_gaps_by_operational_meaning(audit_result):
    generator = GapReportGenerator(client=None)

    model = generator.build_view_model(
        audit_result=audit_result,
        passport_id="demo-passport",
        generated_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )

    assert model["product_context"]["product_name"] == "Canvas Tote Bag"
    assert model["readiness"]["score"] == 42
    assert model["publication_blockers"]["has_blockers"] is True
    assert model["gap_counts"] == {
        "total": 3,
        "blocking": 1,
        "missing": 0,
        "weak_evidence": 1,
        "unverified": 1,
        "recommended": 0,
    }
    assert model["gap_groups"]["blocking"][0]["field"] == "operator_identifier"
    assert model["gap_groups"]["weak_evidence"][0]["field"] == "fiber_composition"
    assert model["gap_groups"]["unverified"][0]["field"] == "declaration_of_conformity"
    assert model["audit_metadata"] == {
        "source": "DataAuditAgent",
        "raw_agent_outputs_included": False,
        "dpp_json_used_as_source": False,
    }


def test_generate_does_not_mutate_audit_result(tmp_path, audit_result):
    before = copy.deepcopy(audit_result)

    GapReportGenerator(client=None).generate(
        audit_result=audit_result,
        output_dir=tmp_path,
        passport_id="demo-passport",
        generated_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )

    assert audit_result == before


def test_failed_audit_result_is_rejected(tmp_path):
    generator = GapReportGenerator(client=None)

    with pytest.raises(ValueError, match="successful DataAuditAgent"):
        generator.generate(
            audit_result={"success": False, "error": "audit failed"},
            output_dir=tmp_path,
        )


def test_deprecated_generator_first_gap_analysis_stays_blocked():
    generator = GapReportGenerator(client=None)

    with pytest.raises(RuntimeError, match="deprecated"):
        generator.analyze_gaps(passport_json={}, required_fields=[])
