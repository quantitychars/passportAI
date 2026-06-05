"""
tests/test_agents.py — PassportAI agent integration tests

Strategy: tests activate as agents are implemented.
- Each class has a skip marker that gets removed when the agent is real.
- Run: pytest tests/test_agents.py -v

Current status:
    ✅ TestBaseAgentContract    — BaseAgent v2.1 (шаг 1.3 DONE)
    ⏳ TestGS1Specialist        — activate on day 8 (шаг 3.5)
    ⏳ TestDataAuditRuleBased   — activate on day 4 (шаг 3.4)
    ⏳ TestLegalAgentSVHC       — activate on day 6 (шаг 3.2)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# Keep the real src package importable for full-suite collection. Agent tests pass
# client=None, so importing GemmaClient for type references must not be mocked.


# ===========================================================================
# ✅ ACTIVE — BaseAgent contract (шаг 1.3 DONE)
# ===========================================================================

class TestBaseAgentContract:
    """BaseAgent v2.1 contract: AgentResult shape, helper methods, safety."""

    @pytest.fixture
    def agent(self):
        from agents.base_agent import BaseAgent

        class _TestAgent(BaseAgent):
            def run(self, **kwargs):
                return self._format_success({"ok": True})

        return _TestAgent(client=None)

    def test_success_result_shape(self, agent):
        """_format_success returns correct AgentResult shape."""
        result = agent._format_success({"field": "value"})
        assert result["success"] is True
        assert result["agent"] == "_TestAgent"
        assert result["is_mock"] is False
        assert "data" in result
        assert "error" not in result

    def test_error_result_shape(self, agent):
        """_format_error returns correct AgentResult shape."""
        result = agent._format_error(ValueError("boom"))
        assert result["success"] is False
        assert result["agent"] == "_TestAgent"
        assert result["error"] == "boom"
        assert "data" not in result

    def test_error_accepts_string(self, agent):
        """_format_error accepts plain string as well as Exception."""
        result = agent._format_error("plain string error")
        assert result["success"] is False
        assert result["error"] == "plain string error"

    def test_run_returns_agent_result(self, agent):
        """run() returns AgentResult via _format_success."""
        result = agent.run()
        assert result["success"] is True
        assert result["data"] == {"ok": True}

    def test_call_tool_without_client_raises(self, agent):
        """call_tool() with client=None raises RuntimeError immediately."""
        with pytest.raises(RuntimeError, match="_TestAgent"):
            agent.call_tool("prompt", [])

    def test_run_verified_task_without_client_raises(self, agent):
        """run_verified_task() with client=None raises RuntimeError."""
        with pytest.raises(RuntimeError, match="_TestAgent"):
            agent.run_verified_task("prompt", [])

    def test_think_without_client_raises(self, agent):
        """think() with client=None raises RuntimeError."""
        with pytest.raises(RuntimeError, match="_TestAgent"):
            agent.think("prompt")

    def test_load_prompt_path_traversal_blocked(self, agent):
        """_load_prompt blocks path traversal attempts."""
        with pytest.raises((ValueError, FileNotFoundError)):
            agent._load_prompt("../../../etc/passwd")

    def test_load_prompt_missing_file_raises(self, agent):
        """_load_prompt raises FileNotFoundError for missing prompt."""
        with pytest.raises(FileNotFoundError):
            agent._load_prompt("nonexistent_prompt_xyz")

    def test_evidence_schema_injection(self, agent):
        """_with_evidence_schema injects evidence into tool parameters."""
        tool = {
            "function": {
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            }
        }
        injected = agent._with_evidence_schema(tool)
        props = injected["function"]["parameters"]["properties"]
        required = injected["function"]["parameters"]["required"]
        assert "evidence" in props
        assert "evidence" in required
        assert "name" in required  # original field preserved

    def test_evidence_schema_does_not_mutate_original(self, agent):
        """_with_evidence_schema returns deep copy — original unchanged."""
        tool = {
            "function": {
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            }
        }
        agent._with_evidence_schema(tool)
        assert "evidence" not in tool["function"]["parameters"]["properties"]

    def test_with_evidence_schema_many(self, agent):
        """_with_evidence_schema_many injects into all tools."""
        tools = [
            {"function": {"parameters": {"type": "object",
             "properties": {}, "required": []}}},
            {"function": {"parameters": {"type": "object",
             "properties": {}, "required": []}}},
        ]
        result = agent._with_evidence_schema_many(tools)
        assert len(result) == 2
        for t in result:
            assert "evidence" in t["function"]["parameters"]["properties"]

    def test_is_mock_false_by_default(self, agent):
        """IS_MOCK is False for real agents."""
        assert agent.IS_MOCK is False

    def test_mock_agent_flag(self):
        """IS_MOCK=True propagates to AgentResult.is_mock."""
        from agents.base_agent import BaseAgent

        class _MockAgent(BaseAgent):
            IS_MOCK = True
            def run(self, **kwargs):
                return self._format_success({"mocked": True})

        mock_agent = _MockAgent(client=None)
        result = mock_agent.run()
        assert result["is_mock"] is True


# ===========================================================================
# ⏳ PENDING — GS1Specialist (activate on day 8, шаг 3.5)
# ===========================================================================

@pytest.mark.skip(reason="GS1Specialist not yet implemented — activate on day 8")
class TestGS1Specialist:
    """GTIN-14 checksum, DID:web generation, GS1 Digital Link format."""

    @pytest.fixture
    def gs1(self):
        from agents.gs1_specialist import GS1Specialist
        return GS1Specialist(client=None)

    def test_valid_gtin14(self, gs1):
        assert gs1.validate_gtin("05901234123457") is True

    def test_invalid_gtin14_wrong_checksum(self, gs1):
        assert gs1.validate_gtin("05901234123458") is False

    def test_invalid_too_short(self, gs1):
        assert gs1.validate_gtin("123") is False

    def test_gtin_with_spaces(self, gs1):
        assert gs1.validate_gtin("0590 1234 1234 57") is True

    def test_did_format(self, gs1):
        uuid = "3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b"
        did = gs1.generate_did_web(uuid)
        assert did.startswith("did:web:")
        assert uuid in did

    def test_gs1_digital_link_format(self, gs1):
        link = gs1.build_gs1_digital_link("5901234123457", "https://example.com")
        assert link.startswith("https://example.com/01/")

    def test_gs1_digital_link_pads_gtin(self, gs1):
        link = gs1.build_gs1_digital_link("123456789", "https://example.com")
        assert "/01/00000123456789" in link


# ===========================================================================
# ⏳ PENDING — DataAuditAgent (activate on day 4, шаг 3.4)
# ===========================================================================

class TestDataAuditAgent:
    """Cross-agent audit synthesis — deterministic, no Ollama required."""

    @pytest.fixture
    def agent(self):
        from agents.data_audit_agent import DataAuditAgent
        return DataAuditAgent(client=None)

    def _domain_data(self, product_group="textiles", *, misaligned=False):
        selected_group = "batteries" if misaligned else product_group

        sectoral = {
            "textiles": {} if selected_group == "textiles" else None,
            "batteries": {} if selected_group == "batteries" else None,
            "electrical_appliances": {} if selected_group == "electrical_appliances" else None,
        }

        expected_profile = {
            "textiles": "textile_core_v1",
            "batteries": "battery_passport_annex_xiii_v1",
            "electrical_appliances": "electrical_appliance_espr_ready_v1",
        }[product_group]

        return {
            "espr_core": {
                "product_group": product_group,
                "espr_category": product_group,
                "sector_profile": {
                    "name": expected_profile,
                    "version": "1.0",
                    "regulatory_source": ["REG_2024_1781_ESPR"],
                },
                "visible_certifications": [],
            },
            "sectoral": sectoral,
            "voluntary_esg": None,
        }

    def _success_envelope(self, payload):
        return {
            "success": True,
            "agent": "UpstreamAgent",
            "is_mock": True,
            "data": payload,
        }

    def _agent_payload(
        self,
        *,
        missing_fields=None,
        warnings=None,
        contradictions=None,
        needs_human_review=False,
        confidence_source="insufficient_data",
        agent_summary="ok",
        recommended_next_actions=None,
        where_to_get_data=None,
        domain_data=None,
    ):
        return {
            "domain_data": domain_data or {
                "espr_core": {},
                "sectoral": {
                    "textiles": None,
                    "batteries": None,
                    "electrical_appliances": None,
                },
            },
            "assessment": {
                "confidence_source": confidence_source,
                "missing_fields": missing_fields or [],
                "warnings": warnings or [],
                "assumptions": [],
                "contradictions": contradictions or [],
                "needs_human_review": needs_human_review,
            },
            "advisory": {
                "agent_summary": agent_summary,
                "business_risks": [],
                "recommended_next_actions": recommended_next_actions or [],
                "supplier_requests": [],
                "where_to_get_data": where_to_get_data or [],
                "next_batch_improvements": [],
            },
        }

    def _missing_field(
        self,
        *,
        field="espr_core.identifiers_hint.gtin",
        severity="required",
        reason="Identifier is missing from trusted input.",
        reason_code="missing",
        source_domain="gs1",
        blocking=False,
        current_evidence_status="absent",
        acceptable_evidence=None,
        closure_condition=None,
        why_it_matters="Stable identifier evidence is needed for traceability.",
        owner_hint="brand_owner",
        where_to_get_data="ERP, PIM, barcode registry, or trusted product master data",
        action="Provide the authoritative identifier from master data.",
        can_be_inferred=False,
        requires_supplier_confirmation=False,
    ):
        return {
            "field": field,
            "severity": severity,
            "reason": reason,
            "reason_code": reason_code,
            "action": action,
            "regulatory_basis": None,
            "deadline": None,
            "can_be_inferred": can_be_inferred,
            "requires_supplier_confirmation": requires_supplier_confirmation,
            "source_domain": source_domain,
            "gap_id": f"{field}:{reason_code}",
            "blocking": blocking,
            "source_agents": ["GS1Specialist"],
            "current_evidence_status": current_evidence_status,
            "closure_condition": closure_condition
            or f"Provide authoritative evidence for {field}.",
            "acceptable_evidence": acceptable_evidence or ["system_export", "document"],
            "why_it_matters": why_it_matters,
            "owner_hint": owner_hint,
            "where_to_get_data": where_to_get_data,
        }

    def test_run_returns_base_agent_envelope(self, agent):
        result = agent.run(
            reconciled_domain_data=self._domain_data(),
        )
        assert result["success"] is True
        assert result["agent"] == "DataAuditAgent"
        assert result["is_mock"] is True
        assert "data" in result

    def test_dedupes_same_gap_and_collects_source_agents(self, agent):
        regulatory_gap = self._missing_field(
            field="espr_core.identifiers_hint.gtin",
            reason="Identifier required for traceability is missing.",
            reason_code="missing",
            source_domain="regulatory",
            owner_hint="internal_compliance",
            acceptable_evidence=["document"],
            where_to_get_data="classification worksheet or compliance file",
            action="Confirm the required identifier from compliance records.",
        )
        legal_gap = self._missing_field(
            field="espr_core.identifiers_hint.gtin",
            reason="No documentary support for identifier value was provided.",
            reason_code="missing",
            source_domain="legal",
            owner_hint="internal_compliance",
            acceptable_evidence=["document"],
            where_to_get_data="declaration of conformity or technical documentation",
            action="Provide documentary support for the identifier.",
        )

        regulatory_result = self._success_envelope(
            self._agent_payload(
                missing_fields=[regulatory_gap],
                agent_summary="regulatory ok",
            )
        )
        legal_result = self._success_envelope(
            self._agent_payload(
                missing_fields=[legal_gap],
                agent_summary="legal ok",
            )
        )

        result = agent.run(
            reconciled_domain_data=self._domain_data(),
            regulatory_result=regulatory_result,
            legal_result=legal_result,
        )

        data = result["data"]
        gaps = data["assessment"]["missing_fields"]

        assert len(gaps) == 1
        assert gaps[0]["field"] == "espr_core.identifiers_hint.gtin"
        assert gaps[0]["reason_code"] == "missing"
        assert set(gaps[0]["source_agents"]) == {"RegulatoryConsultant", "LegalAgent"}

    def test_blocked_by_conflicts_when_final_state_is_misaligned(self, agent):
        result = agent.run(
            reconciled_domain_data=self._domain_data(product_group="textiles", misaligned=True),
        )

        assessment = result["data"]["assessment"]
        assert assessment["readiness_verdict"] == "blocked_by_conflicts"
        assert assessment["is_publishable"] is False
        assert len(assessment["contradictions"]) > 0

    def test_not_ready_when_blocking_gap_exists(self, agent):
        legal_gap = self._missing_field(
            field="espr_core.compliance_hint.declaration_of_conformity",
            severity="required",
            reason="Declaration of conformity document is absent.",
            reason_code="document_absent",
            source_domain="legal",
            current_evidence_status="absent",
            acceptable_evidence=["document"],
            owner_hint="internal_compliance",
            where_to_get_data="declaration of conformity or technical documentation",
            action="Provide the declaration of conformity document.",
        )

        legal_result = self._success_envelope(
            self._agent_payload(
                missing_fields=[legal_gap],
                agent_summary="legal gap found",
            )
        )

        result = agent.run(
            reconciled_domain_data=self._domain_data(),
            legal_result=legal_result,
        )

        assessment = result["data"]["assessment"]
        assert assessment["readiness_verdict"] == "not_ready"
        assert assessment["is_publishable"] is False
        assert len(assessment["blocking_issues"]) > 0

    def test_ready_with_gaps_is_not_publishable_when_human_review_needed(self, agent):
        legal_result = self._success_envelope(
            self._agent_payload(
                missing_fields=[],
                needs_human_review=True,
                agent_summary="human review required",
            )
        )

        result = agent.run(
            reconciled_domain_data=self._domain_data(),
            legal_result=legal_result,
        )

        assessment = result["data"]["assessment"]
        assert assessment["readiness_verdict"] == "ready_with_gaps"
        assert assessment["needs_human_review"] is True
        assert assessment["is_publishable"] is False

    def test_ready_when_no_gaps_conflicts_or_review_flags(self, agent):
        result = agent.run(
            reconciled_domain_data=self._domain_data(),
            vision_result=self._success_envelope(self._agent_payload(agent_summary="vision ok")),
            regulatory_result=self._success_envelope(self._agent_payload(agent_summary="reg ok")),
            legal_result=self._success_envelope(self._agent_payload(agent_summary="legal ok")),
            lca_result=self._success_envelope(self._agent_payload(agent_summary="lca ok")),
            gs1_result=self._success_envelope(self._agent_payload(agent_summary="gs1 ok")),
        )

        assessment = result["data"]["assessment"]
        assert assessment["readiness_verdict"] == "ready"
        assert assessment["readiness_score"] >= 90
        assert assessment["is_publishable"] is True
        assert assessment["missing_fields"] == []
        assert assessment["contradictions"] == []


class TestDataAuditValidation:
    """Validator coverage for the new DataAuditAgent contract."""

    @pytest.fixture
    def agent(self):
        from agents.data_audit_agent import DataAuditAgent
        return DataAuditAgent(client=None)

    @pytest.fixture
    def valid_payload(self, agent):
        result = agent.run(
            reconciled_domain_data={
                "espr_core": {
                    "product_group": "textiles",
                    "espr_category": "textiles",
                    "sector_profile": {
                        "name": "textile_core_v1",
                        "version": "1.0",
                        "regulatory_source": ["REG_2024_1781_ESPR"],
                    },
                    "visible_certifications": [],
                },
                "sectoral": {
                    "textiles": {},
                    "batteries": None,
                    "electrical_appliances": None,
                },
                "voluntary_esg": None,
            },
        )
        assert result["success"] is True
        return result["data"]

    def test_valid_payload_passes_validation(self, valid_payload):
        from agents.validation import validate_agent_output

        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert errors == []

    def test_missing_reason_code_fails_validation(self, valid_payload):
        from agents.validation import validate_agent_output

        valid_payload["assessment"]["missing_fields"] = [
            {
                "field": "espr_core.identifiers_hint.gtin",
                "severity": "required",
                "reason": "Identifier is missing.",
                "action": "Provide identifier.",
                "regulatory_basis": None,
                "deadline": None,
                "can_be_inferred": False,
                "requires_supplier_confirmation": False,
                "source_domain": "gs1",
                "gap_id": "espr_core.identifiers_hint.gtin:missing",
                "blocking": True,
                "source_agents": ["GS1Specialist"],
                "current_evidence_status": "absent",
                "closure_condition": "Provide authoritative identifier evidence.",
                "acceptable_evidence": ["system_export", "document"],
                "why_it_matters": "Identifier evidence is needed for traceability.",
                "owner_hint": "brand_owner",
                "where_to_get_data": "ERP or barcode registry",
            }
        ]

        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert any("reason_code" in err for err in errors)

    def test_invalid_readiness_verdict_fails_validation(self, valid_payload):
        from agents.validation import validate_agent_output

        valid_payload["assessment"]["readiness_verdict"] = "draftish"

        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert any("readiness_verdict" in err for err in errors)

    def test_readiness_score_out_of_range_fails_validation(self, valid_payload):
        from agents.validation import validate_agent_output

        valid_payload["assessment"]["readiness_score"] = 101

        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert any("readiness_score" in err for err in errors)

    def test_empty_missing_fields_is_allowed(self, valid_payload):
        from agents.validation import validate_agent_output

        valid_payload["assessment"]["missing_fields"] = []
        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert not any("missing_fields must be a non-empty list" in err for err in errors)

    def test_empty_recommended_next_actions_is_allowed(self, valid_payload):
        from agents.validation import validate_agent_output

        valid_payload["advisory"]["recommended_next_actions"] = []
        errors = validate_agent_output("DataAuditAgent", valid_payload)
        assert not any("recommended_next_actions must be a non-empty list" in err for err in errors)


# ===========================================================================
# ⏳ PENDING — LegalAgent SVHC scan (activate on day 6, шаг 3.2)
# ===========================================================================

@pytest.mark.skip(reason="LegalAgent not yet implemented — activate on day 6")
class TestLegalAgentSVHC:
    """REACH SVHC pre-filter — no Ollama required."""

    @pytest.fixture
    def agent(self):
        from agents.legal_agent import LegalAgent
        return LegalAgent(client=None, enable_vies=False)

    def test_neodymium_flagged(self, agent):
        flags = agent._quick_svhc_scan(
            [{"material": "Neodymium magnet", "percentage": 5}]
        )
        assert len(flags) > 0
        assert any("neodymium" in f.lower() for f in flags)

    def test_lead_flagged(self, agent):
        flags = agent._quick_svhc_scan(
            [{"material": "Lead solder", "percentage": 1}]
        )
        assert len(flags) > 0

    def test_cotton_not_flagged(self, agent):
        flags = agent._quick_svhc_scan(
            [{"material": "Organic cotton", "percentage": 100}]
        )
        assert flags == []

    def test_empty_composition_no_flags(self, agent):
        assert agent._quick_svhc_scan([]) == []

    def test_case_insensitive(self, agent):
        flags = agent._quick_svhc_scan(
            [{"material": "NEODYMIUM ALLOY", "percentage": 3}]
        )
        assert len(flags) > 0