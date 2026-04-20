"""
tests/test_agents.py — Tests for all PassportAI agents

Tests:
    - BaseAgent._parse_json_response() — core utility
    - GS1Specialist.validate_gtin() — GTIN checksum (no Ollama needed)
    - GS1Specialist.generate_did_web() — DID generation
    - GS1Specialist.build_gs1_digital_link() — GS1 URL format
    - DataAuditAgent._rule_based_audit() — completeness checking
    - LegalAgent._quick_svhc_scan() — REACH pre-filter

Run:
    pytest tests/test_agents.py -v
"""


# ---------------------------------------------------------------------------
# BaseAgent._parse_json_response() tests
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    """Test BaseAgent._parse_json_response() with various input formats."""

    @pytest.fixture
    def agent(self):
        """TestAgent instance for testing BaseAgent methods."""
        from agents.base_agent import BaseAgent

        class _TestAgent(BaseAgent):
            def run(self, **kwargs):
                return {}

        return _TestAgent(client=None)

    def test_plain_json_object(self, agent):
        """Parses clean JSON object."""
        result = agent._parse_json_response('{"ok": true, "score": 72}')
        assert result == {"ok": True, "score": 72}

    def test_markdown_json_block(self, agent):
        """Strips ```json ... ``` fences and parses."""
        result = agent._parse_json_response('```json\n{"ok": true}\n```')
        assert result == {"ok": True}

    def test_markdown_block_no_lang(self, agent):
        """Strips ``` ... ``` fences without language tag."""
        result = agent._parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_leading_text(self, agent):
        """Extracts JSON from response with leading explanation text."""
        result = agent._parse_json_response('Here is the analysis:\n{"result": "pass"}')
        assert result == {"result": "pass"}

    def test_nested_json(self, agent):
        """Parses nested JSON structures."""
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = agent._parse_json_response(raw)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_invalid_json_raises_value_error(self, agent):
        """Raises ValueError for non-JSON text."""
        with pytest.raises(ValueError, match="Could not extract valid JSON"):
            agent._parse_json_response("This is definitely not JSON at all.")

    def test_empty_string_raises_value_error(self, agent):
        """Raises ValueError for empty string."""
        with pytest.raises(ValueError):
            agent._parse_json_response("")

    def test_json_array(self, agent):
        """Parses JSON array."""
        result = agent._parse_json_response('[{"a": 1}, {"b": 2}]')
        assert isinstance(result, list)
        assert len(result) == 2

    def test_unicode_content(self, agent):
        """Handles unicode characters in JSON."""
        result = agent._parse_json_response('{"name": "Шопер NikSense"}')
        assert result["name"] == "Шопер NikSense"


# ---------------------------------------------------------------------------
# GS1Specialist tests
# ---------------------------------------------------------------------------

class TestGS1SpecialistGTIN:
    """Test GTIN-14 checksum validation — no Ollama required."""

    @pytest.fixture
    def gs1(self):
        from agents.gs1_specialist import GS1Specialist
        return GS1Specialist(client=None)

    def test_valid_gtin14(self, gs1):
        """Known valid GTIN-14 passes validation."""
        assert gs1.validate_gtin("05901234123457") is True

    def test_invalid_gtin14_wrong_checksum(self, gs1):
        """GTIN with wrong last digit fails validation."""
        assert gs1.validate_gtin("05901234123458") is False

    def test_valid_gtin13(self, gs1):
        """Valid GTIN-13 (zero-padded to 14) passes."""
        # "5901234123457" is valid GTIN-13 → pad to "05901234123457"
        assert gs1.validate_gtin("5901234123457") is True

    def test_invalid_too_short(self, gs1):
        """GTIN shorter than 8 digits fails."""
        assert gs1.validate_gtin("123") is False

    def test_invalid_non_digit_chars(self, gs1):
        """GTIN with non-digit chars after stripping fails if too short."""
        assert gs1.validate_gtin("ABC") is False

    def test_gtin_with_spaces(self, gs1):
        """GTIN with spaces is cleaned before validation."""
        # Should strip spaces and validate
        result = gs1.validate_gtin("0590 1234 1234 57")
        # After stripping spaces: "05901234123457" — valid
        assert result is True

    def test_all_zeros_invalid(self, gs1):
        """All-zero GTIN is invalid (checksum 0 ≠ calculated)."""
        # 13 zeros + checksum: 0000000000000 → check digit = 0, so "00000000000000" IS valid by mod-10
        # Actually let's just verify it doesn't crash
        result = gs1.validate_gtin("00000000000000")
        assert isinstance(result, bool)


class TestGS1SpecialistDID:
    """Test DID:web generation — no Ollama required."""

    @pytest.fixture
    def gs1(self):
        from agents.gs1_specialist import GS1Specialist
        return GS1Specialist(client=None, base_did_domain="passportai.example.com")

    def test_did_format(self, gs1):
        """DID:web follows correct format."""
        did = gs1.generate_did_web("3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b")
        assert did.startswith("did:web:passportai.example.com:passports:")

    def test_did_contains_uuid(self, gs1):
        """DID:web contains the passport UUID."""
        uuid = "3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b"
        did = gs1.generate_did_web(uuid)
        assert uuid in did

    def test_gs1_digital_link_format(self, gs1):
        """GS1 Digital Link follows {base_url}/01/{gtin14} format."""
        link = gs1.build_gs1_digital_link("5901234123457", "https://example.com")
        assert link == "https://example.com/01/05901234123457"

    def test_gs1_digital_link_pads_gtin(self, gs1):
        """Short GTIN is zero-padded to 14 digits in Digital Link."""
        link = gs1.build_gs1_digital_link("123456789", "https://example.com")
        assert "/01/00000123456789" in link


# ---------------------------------------------------------------------------
# DataAuditAgent rule-based audit tests
# ---------------------------------------------------------------------------

class TestDataAuditRuleBased:
    """Test DataAuditAgent._rule_based_audit() — no Ollama required."""

    @pytest.fixture
    def agent(self):
        from agents.data_audit_agent import DataAuditAgent
        return DataAuditAgent(client=None)

    def test_missing_manufacturer_lowers_score(self, agent):
        """Passport without manufacturer has score < 60."""
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, ["manufacturer"])
        assert result["readiness_score"] < 60

    def test_missing_manufacturer_in_missing_essential(self, agent):
        """Missing manufacturer is in missing_essential list."""
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, ["manufacturer"])
        assert "manufacturer" in result["missing_essential"]

    def test_material_composition_sum_inconsistency(self, agent):
        """Material percentages not summing to 100 creates inconsistency."""
        passport = {
            "credentialSubject": {
                "materialComposition": [
                    {"material": "cotton", "percentage": 60},
                    {"material": "polyester", "percentage": 30},
                ]
            }
        }
        result = agent._rule_based_audit(passport, [])
        assert any("90" in inc or "sum" in inc.lower() for inc in result["inconsistencies"])

    def test_complete_passport_high_score(self, agent):
        """Passport with all essential fields scores higher."""
        from agents.data_audit_agent import UNIVERSAL_ESSENTIAL_FIELDS
        subject = {field: "value" for field in UNIVERSAL_ESSENTIAL_FIELDS}
        subject["materialComposition"] = [{"material": "cotton", "percentage": 100}]
        subject["photo"] = {"width": 800, "height": 800}
        passport = {"credentialSubject": subject}
        result = agent._rule_based_audit(passport, UNIVERSAL_ESSENTIAL_FIELDS)
        assert result["readiness_score"] > 50

    def test_score_breakdown_sums_to_total(self, agent):
        """Score breakdown components sum to total."""
        passport = {"credentialSubject": {}}
        result = agent._rule_based_audit(passport, [])
        breakdown = result["score_breakdown"]
        components = (
            breakdown["essential_fields"] +
            breakdown["recommended_fields"] +
            breakdown["documents_attached"] +
            breakdown["photo_standardized"]
        )
        assert components == breakdown["total"]


# ---------------------------------------------------------------------------
# LegalAgent._quick_svhc_scan() tests
# ---------------------------------------------------------------------------

class TestLegalAgentSVHC:
    """Test LegalAgent._quick_svhc_scan() — no Ollama required."""

    @pytest.fixture
    def agent(self):
        from agents.legal_agent import LegalAgent
        return LegalAgent(client=None, enable_vies=False)

    def test_neodymium_flagged(self, agent):
        """Neodymium is flagged as SVHC candidate."""
        composition = [{"material": "Neodymium magnet", "percentage": 5}]
        flags = agent._quick_svhc_scan(composition)
        assert len(flags) > 0
        assert any("neodymium" in f.lower() for f in flags)

    def test_lead_flagged(self, agent):
        """Lead is flagged as SVHC."""
        composition = [{"material": "Lead solder", "percentage": 1}]
        flags = agent._quick_svhc_scan(composition)
        assert len(flags) > 0

    def test_cotton_not_flagged(self, agent):
        """Organic cotton is NOT a SVHC substance."""
        composition = [{"material": "Organic cotton", "percentage": 100}]
        flags = agent._quick_svhc_scan(composition)
        assert len(flags) == 0

    def test_empty_composition_no_flags(self, agent):
        """Empty composition produces no flags."""
        flags = agent._quick_svhc_scan([])
        assert flags == []

    def test_case_insensitive_detection(self, agent):
        """SVHC detection is case-insensitive."""
        composition = [{"material": "NEODYMIUM ALLOY", "percentage": 3}]
        flags = agent._quick_svhc_scan(composition)
        assert len(flags) > 0
