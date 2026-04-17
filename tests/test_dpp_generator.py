"""
tests/test_dpp_generator.py — Tests for DPPGenerator

Tests:
    - merge_inputs() — user_input overrides vision_output
    - _compute_content_hash() — deterministic SHA-256
    - _build_jsonld_wrapper() — valid W3C VC structure
    - validate() — catches missing required fields
    - generate_from_text() — requires Ollama (skipped if not available)

Run:
    pytest tests/test_dpp_generator.py -v
    pytest tests/test_dpp_generator.py -v -k "not ollama"
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generator():
    """DPPGenerator instance without Ollama (for structural tests)."""
    from src.core.dpp_generator import DPPGenerator
    return DPPGenerator(client=None)


@pytest.fixture
def sample_credential_subject():
    """Sample credentialSubject for wrapper tests."""
    return {
        "productId": "did:web:example.com:products:test-001",
        "productName": "Test Product",
        "esprCategory": "textiles",
        "economicOperator": {"name": "Test Co"},
        "materialComposition": [{"material": "cotton", "percentage": 100}],
        "countryOfManufacture": "UA",
        "dppIssuer": "PassportAI",
        "dppVersion": "1.0",
        "dppIssuedAt": "2025-04-13T00:00:00Z",
        "dppValidUntil": "2035-04-13T00:00:00Z",
    }


@pytest.fixture
def minimal_valid_passport(generator, sample_credential_subject):
    """Minimal valid passport for validation tests."""
    return generator._build_jsonld_wrapper(sample_credential_subject)


# ---------------------------------------------------------------------------
# merge_inputs tests
# ---------------------------------------------------------------------------

class TestMergeInputs:
    """Test DPPGenerator.merge_inputs() user_input priority rule."""

    def test_user_input_overrides_vision(self, generator):
        """user_input values take priority over vision_output on conflict."""
        vision = {"category": "electronics", "materials": ["plastic"]}
        user = {"category": "textiles"}
        merged = generator.merge_inputs(vision, user)
        assert merged["category"] == "textiles", "user_input must win on conflict"

    def test_vision_fills_missing_user_fields(self, generator):
        """Fields in vision_output but not user_input are preserved."""
        vision = {"category": "textiles", "colors": ["beige"]}
        user = {"description": "Tote bag"}
        merged = generator.merge_inputs(vision, user)
        assert merged["colors"] == ["beige"], "Vision fields should be preserved"
        assert merged["description"] == "Tote bag", "User fields should be preserved"

    def test_empty_user_input(self, generator):
        """Empty user_input returns vision_output unchanged."""
        vision = {"category": "textiles", "materials": ["cotton"]}
        merged = generator.merge_inputs(vision, {})
        assert merged == vision

    def test_empty_vision_output(self, generator):
        """Empty vision_output returns user_input unchanged."""
        user = {"description": "Cotton tote bag"}
        merged = generator.merge_inputs({}, user)
        assert merged == user

    def test_all_fields_conflict(self, generator):
        """When all fields conflict, user_input wins for all."""
        vision = {"a": 1, "b": 2, "c": 3}
        user = {"a": 10, "b": 20, "c": 30}
        merged = generator.merge_inputs(vision, user)
        assert merged == {"a": 10, "b": 20, "c": 30}


# ---------------------------------------------------------------------------
# Content hash tests
# ---------------------------------------------------------------------------

class TestContentHash:
    """Test _compute_content_hash() determinism."""

    def test_hash_is_deterministic(self, generator):
        """Same input always produces same hash."""
        subject = {"productName": "Test", "esprCategory": "textiles"}
        hash1 = generator._compute_content_hash(subject)
        hash2 = generator._compute_content_hash(subject)
        assert hash1 == hash2

    def test_hash_is_key_order_independent(self, generator):
        """Hash is the same regardless of key insertion order."""
        subject_a = {"productName": "Test", "esprCategory": "textiles"}
        subject_b = {"esprCategory": "textiles", "productName": "Test"}
        assert generator._compute_content_hash(subject_a) == generator._compute_content_hash(subject_b)

    def test_hash_changes_with_content(self, generator):
        """Different content produces different hashes."""
        subject_a = {"productName": "Product A"}
        subject_b = {"productName": "Product B"}
        assert generator._compute_content_hash(subject_a) != generator._compute_content_hash(subject_b)

    def test_hash_is_sha256_hex(self, generator):
        """Hash is a 64-character lowercase hex string."""
        subject = {"productName": "Test"}
        hash_value = generator._compute_content_hash(subject)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


# ---------------------------------------------------------------------------
# JSON-LD wrapper tests
# ---------------------------------------------------------------------------

class TestBuildJsonldWrapper:
    """Test _build_jsonld_wrapper() produces valid W3C VC structure."""

    def test_required_fields_present(self, minimal_valid_passport):
        """Wrapper includes all required W3C VC fields."""
        required = ["@context", "id", "type", "issuer", "validFrom", "validUntil",
                    "contentHash", "credentialSubject"]
        for field in required:
            assert field in minimal_valid_passport, f"Missing field: {field}"

    def test_type_includes_verifiable_credential(self, minimal_valid_passport):
        """type array must include VerifiableCredential."""
        assert "VerifiableCredential" in minimal_valid_passport["type"]

    def test_type_includes_dpp(self, minimal_valid_passport):
        """type array must include DigitalProductPassport."""
        assert "DigitalProductPassport" in minimal_valid_passport["type"]

    def test_content_hash_format(self, minimal_valid_passport):
        """contentHash matches sha256: prefix + 64 hex chars."""
        import re
        assert re.match(r"^sha256:[a-f0-9]{64}$", minimal_valid_passport["contentHash"])

    def test_context_includes_w3c_vc(self, minimal_valid_passport):
        """@context includes the W3C credentials v2 URI."""
        contexts = minimal_valid_passport["@context"]
        assert any("credentials/v2" in str(c) for c in contexts)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidate:
    """Test DPPGenerator.validate() catches structural issues."""

    def test_valid_passport_passes(self, generator, minimal_valid_passport):
        """A well-formed passport passes validation."""
        valid, errors = generator.validate(minimal_valid_passport)
        assert valid is True, f"Expected valid, got errors: {errors}"
        assert errors == []

    def test_missing_context_fails(self, generator, minimal_valid_passport):
        """Passport without @context fails validation."""
        del minimal_valid_passport["@context"]
        valid, errors = generator.validate(minimal_valid_passport)
        assert valid is False
        assert any("@context" in e for e in errors)

    def test_missing_credential_subject_fails(self, generator, minimal_valid_passport):
        """Passport without credentialSubject fails validation."""
        del minimal_valid_passport["credentialSubject"]
        valid, errors = generator.validate(minimal_valid_passport)
        assert valid is False
        assert any("credentialSubject" in e for e in errors)

    def test_missing_type_fails(self, generator, minimal_valid_passport):
        """Passport without VerifiableCredential in type fails."""
        minimal_valid_passport["type"] = ["SomeOtherType"]
        valid, errors = generator.validate(minimal_valid_passport)
        assert valid is False

    def test_empty_passport_fails(self, generator):
        """Empty dict fails validation with multiple errors."""
        valid, errors = generator.validate({})
        assert valid is False
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Integration tests (require Ollama)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    True,  # Always skip until implemented
    reason="Requires Ollama with gemma4:e4b — set SKIP_OLLAMA_TESTS=false"
)
class TestGenerateFromText:
    """Integration tests requiring a running Ollama server."""

    def test_generate_returns_passport(self):
        """generate_from_text() returns a valid passport dict."""
        # from src.core.gemma_client import GemmaClient
        # from src.core.dpp_generator import DPPGenerator
        # client = GemmaClient()
        # gen = DPPGenerator(client)
        # passport = gen.generate_from_text("Cotton tote bag, made in Ukraine")
        # assert "@context" in passport
        # assert "credentialSubject" in passport
        pytest.skip("Not yet implemented")
