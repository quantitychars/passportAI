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
from unittest.mock import MagicMock

# Mock GemmaClient before any agent imports
_mock = MagicMock()
sys.modules.setdefault("src", _mock)
sys.modules.setdefault("src.core", _mock)
sys.modules.setdefault("src.core.gemma_client", _mock)
_mock.GemmaClient = MagicMock


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

@pytest.mark.skip(reason="DataAuditAgent not yet implemented — activate on day 4")
class TestDataAuditRuleBased:
    """Rule-based completeness audit — no Ollama required."""

    @pytest.fixture
    def agent(self):
        from agents.data_audit_agent import DataAuditAgent
        return DataAuditAgent(client=None)

    def test_missing_manufacturer_lowers_score(self, agent):
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, ["manufacturer"])
        assert result["readiness_score"] < 60

    def test_missing_manufacturer_in_missing_essential(self, agent):
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, ["manufacturer"])
        assert "manufacturer" in result["missing_essential"]

    def test_score_breakdown_sums_to_total(self, agent):
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, [])
        breakdown = result["score_breakdown"]
        total = (
            breakdown["essential_fields"]
            + breakdown["recommended_fields"]
            + breakdown["documents_attached"]
            + breakdown["photo_standardized"]
        )
        assert total == breakdown["total"]

    def test_material_sum_inconsistency_flagged(self, agent):
        passport = {
            "credentialSubject": {
                "materialComposition": [
                    {"material": "cotton", "percentage": 60},
                    {"material": "polyester", "percentage": 30},
                ]
            }
        }
        result = agent._rule_based_audit(passport, [])
        assert len(result["inconsistencies"]) > 0


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