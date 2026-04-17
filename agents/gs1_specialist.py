"""
agents/gs1_specialist.py — GS1 Specialist Agent

Handles GS1 identifiers for Digital Product Passports:
  - GTIN-14 barcode validation (checksum verification)
  - DID:web generation from UUID
  - GS1 Digital Link URL construction

GS1 standards:
  - GTIN: Global Trade Item Number (14 digits, mod-10 checksum)
  - DID:web: Decentralized Identifier using web method
  - GS1 Digital Link: https://www.gs1.org/standards/gs1-digital-link

Usage:
    from agents.gs1_specialist import GS1Specialist

    gs1 = GS1Specialist(gemma_client)

    # Validate GTIN
    assert gs1.validate_gtin("05901234123457") == True
    assert gs1.validate_gtin("05901234123458") == False

    # Generate DID
    did = gs1.generate_did_web("3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b")
    # "did:web:passportai.example.com:passports:3f8a1b2c-..."

    # Build GS1 Digital Link
    url = gs1.build_gs1_digital_link("05901234123457", "https://passportai.example.com")
    # "https://passportai.example.com/01/05901234123457"
"""

import os
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


class GS1Specialist(BaseAgent):
    """GS1 identifier management agent.

    Validates GTINs, generates DID:web identifiers, and builds
    GS1 Digital Link URLs for product passports.

    Does NOT require Gemma 4 for core functions (validate_gtin, generate_did_web,
    build_gs1_digital_link are pure algorithmic — no LLM needed).

    Attributes:
        base_did_domain: Domain for DID:web generation.
        base_url: Base URL for GS1 Digital Links.
    """

    def __init__(
        self,
        client: Any,  # Optional — GS1 functions don't require LLM
        prompts_dir: Path | None = None,
        base_did_domain: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize GS1Specialist.

        Args:
            client: GemmaClient (optional for this agent).
            prompts_dir: Path to prompts directory.
            base_did_domain: Domain for DID:web URLs. Defaults to
                             HOSTING_URL domain or "passportai.example.com".
            base_url: Base URL for GS1 Digital Links. Defaults to HOSTING_URL.
        """
        super().__init__(client, prompts_dir, name="GS1Specialist")
        hosting_url = os.getenv("HOSTING_URL", "http://localhost:8000")
        self.base_did_domain = base_did_domain or "passportai.example.com"
        self.base_url = base_url or hosting_url.rstrip("/")

    def run(
        self,
        passport_json: dict | None = None,
        gtin: str | None = None,
        passport_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Generate product ID and passport URL for the DPP.

        Args:
            passport_json: The passport draft (for enrichment).
            gtin: Optional GTIN-14 barcode string.
            passport_id: UUID of the passport (required).

        Returns:
            Dictionary with:
                - product_id (str): DID:web or GS1 identifier
                - passport_url (str): Public URL for the passport
                - gs1_digital_link (str | None): GS1 Digital Link if GTIN provided
                - gtin_valid (bool | None): GTIN validation result
                - did_web (str): DID:web identifier

        Example:
            >>> gs1 = GS1Specialist(None)
            >>> result = gs1.run(passport_id="abc-123", gtin="05901234123457")
            >>> print(result["passport_url"])  # "http://localhost:8000/abc-123"
        """
        if not passport_id:
            raise ValueError("passport_id is required for GS1Specialist.run()")

        did_web = self.generate_did_web(passport_id)
        passport_url = f"{self.base_url}/{passport_id}"

        result = {
            "product_id": did_web,
            "passport_url": passport_url,
            "did_web": did_web,
            "gs1_digital_link": None,
            "gtin_valid": None,
        }

        if gtin:
            is_valid = self.validate_gtin(gtin)
            result["gtin_valid"] = is_valid
            if is_valid:
                result["gs1_digital_link"] = self.build_gs1_digital_link(gtin, self.base_url)
                result["product_id"] = self.build_gs1_digital_link(gtin, self.base_url)

        return result

    def validate_gtin(self, gtin: str) -> bool:
        """Validate a GS1 GTIN-14 barcode using the mod-10 checksum algorithm.

        The GS1 mod-10 checksum algorithm:
          1. Remove all non-digit characters
          2. The checksum digit is the last digit
          3. Multiply alternating digits by 3 and 1 (starting from right, excluding check digit)
          4. Sum all products
          5. Check digit = (10 - (sum % 10)) % 10

        Accepts GTIN-8, GTIN-12, GTIN-13, GTIN-14 (pads shorter GTINs to 14 digits).

        Args:
            gtin: GTIN string (8, 12, 13, or 14 digits). Non-digit chars are stripped.

        Returns:
            True if the checksum is valid, False otherwise.

        Example:
            >>> gs1 = GS1Specialist(None)
            >>> assert gs1.validate_gtin("05901234123457") == True
            >>> assert gs1.validate_gtin("05901234123458") == False
            >>> assert gs1.validate_gtin("05901234123457") == True  # GTIN-14
        """
        # Strip non-digit characters
        digits = "".join(c for c in gtin if c.isdigit())

        # Valid GTIN lengths: 8, 12, 13, 14
        if len(digits) not in (8, 12, 13, 14):
            return False

        # Pad to 14 digits for uniform processing
        digits = digits.zfill(14)

        # GS1 mod-10 checksum (Luhn variant)
        # Process digits from right to left, excluding check digit (last)
        check_digit = int(digits[-1])
        total = 0
        for i, digit in enumerate(reversed(digits[:-1])):
            # Multiply by 3 if position is even (0-indexed from right), else 1
            multiplier = 3 if i % 2 == 0 else 1
            total += int(digit) * multiplier

        calculated_check = (10 - (total % 10)) % 10
        return calculated_check == check_digit

    def generate_did_web(self, passport_uuid: str) -> str:
        """Generate a DID:web identifier for a passport.

        Format: did:web:{domain}:passports:{uuid}

        Args:
            passport_uuid: UUID string for the passport.

        Returns:
            DID:web identifier string.

        Example:
            >>> gs1 = GS1Specialist(None)
            >>> did = gs1.generate_did_web("3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b")
            >>> print(did)  # "did:web:passportai.example.com:passports:3f8a1b2c-..."
        """
        return f"did:web:{self.base_did_domain}:passports:{passport_uuid}"

    def build_gs1_digital_link(self, gtin: str, base_url: str) -> str:
        """Build a GS1 Digital Link URL for a GTIN.

        GS1 Digital Link format: {base_url}/01/{gtin14}

        The Application Identifier (AI) 01 identifies the GTIN.
        GTIN is zero-padded to 14 digits.

        Args:
            gtin: GTIN string (will be zero-padded to 14 digits).
            base_url: Base URL for the digital link resolver.

        Returns:
            GS1 Digital Link URL string.

        Reference:
            https://www.gs1.org/standards/gs1-digital-link

        Example:
            >>> gs1 = GS1Specialist(None)
            >>> url = gs1.build_gs1_digital_link("5901234123457", "https://example.com")
            >>> print(url)  # "https://example.com/01/05901234123457"
        """
        digits = "".join(c for c in gtin if c.isdigit())
        gtin14 = digits.zfill(14)
        return f"{base_url.rstrip('/')}/01/{gtin14}"


if __name__ == "__main__":
    gs1 = GS1Specialist(None)

    # Test GTIN validation
    valid_gtin = "05901234123457"
    invalid_gtin = "05901234123458"

    print(f"GTIN {valid_gtin}: {gs1.validate_gtin(valid_gtin)}")   # True
    print(f"GTIN {invalid_gtin}: {gs1.validate_gtin(invalid_gtin)}")  # False

    # Test DID generation
    test_uuid = "3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b"
    did = gs1.generate_did_web(test_uuid)
    print(f"DID:web: {did}")

    # Test GS1 Digital Link
    link = gs1.build_gs1_digital_link(valid_gtin, "https://passportai.example.com")
    print(f"GS1 Digital Link: {link}")

    # Assert correctness
    assert gs1.validate_gtin(valid_gtin) is True, "GTIN should be valid"
    assert gs1.validate_gtin(invalid_gtin) is False, "GTIN should be invalid"
    print("\nAll GS1 tests passed!")
