"""
src/core/dpp_generator.py — JSON-LD VCDM 2.0 Digital Product Passport Generator

Orchestrates the full DPP generation pipeline:
  1. Text-only: generate_from_text(description) → passport dict
  2. Multimodal: generate_from_photo_and_text(image_path, description) → passport dict
  3. Input merging: merge_inputs(vision_output, user_input) → unified dict
  4. Validation: validate(passport) → (is_valid, errors)

Output format: JSON-LD VCDM 2.0 Level 2 (see DPP_SCHEMA.json for full structure)

Usage:
    from src.core.gemma_client import GemmaClient
    from src.core.dpp_generator import DPPGenerator

    client = GemmaClient()
    gen = DPPGenerator(client)
    passport = gen.generate_from_text("100% cotton tote bag, made in Ukraine")
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class DPPGenerator:
    """Generates JSON-LD VCDM 2.0 Digital Product Passports.

    Uses Gemma 4 via GemmaClient to populate passport fields from product
    descriptions and images. Validates output against W3C credentials schema.

    Attributes:
        client: GemmaClient instance for LLM calls.
        prompts_dir: Path to the prompts/ directory.
        schemas_dir: Path to the schemas/ directory.
        contexts_dir: Path to the contexts/ directory (cached, offline).
    """

    ISSUER_DID = "did:web:passportai.example.com"
    DPP_VALIDITY_YEARS = 10

    def __init__(
        self,
        client: Any,  # GemmaClient
        prompts_dir: Path | None = None,
        schemas_dir: Path | None = None,
    ) -> None:
        """Initialize DPPGenerator.

        Args:
            client: GemmaClient instance. Can be None for merge/validate-only usage.
            prompts_dir: Path to prompts directory. Defaults to ./prompts.
            schemas_dir: Path to schemas directory. Defaults to ./schemas.
        """
        self.client = client
        self.prompts_dir = prompts_dir or Path("prompts")
        self.schemas_dir = schemas_dir or Path("schemas")
        # TODO: load prompt templates at init time
        # self._dpp_prompt = (self.prompts_dir / "dpp_generation.txt").read_text()

    def generate_from_text(self, description: str) -> dict:
        """Generate a DPP passport from a text description only.

        Calls Gemma 4 with the DPP generation prompt and parses the JSON response.
        No image analysis is performed.

        Args:
            description: Natural language product description (any language).

        Returns:
            Full JSON-LD VCDM 2.0 passport dictionary.

        Raises:
            ValueError: If the model returns invalid JSON.
            RuntimeError: If Gemma client fails.

        Example:
            >>> gen = DPPGenerator(client)
            >>> passport = gen.generate_from_text("Cotton tote bag, Ukraine")
            >>> print(passport["@context"])
        """
        # TODO: implement text-based DPP generation
        # prompt = self._build_dpp_prompt({"description": description})
        # raw = self.client.generate(prompt)
        # passport_data = self._parse_llm_json(raw)
        # return self._build_jsonld_wrapper(passport_data)
        raise NotImplementedError("DPPGenerator.generate_from_text() not yet implemented")

    def generate_from_photo_and_text(
        self,
        image_path: str | Path,
        description: str,
    ) -> dict:
        """Generate a DPP passport from a product photo and text description.

        Runs vision analysis on the image, merges with user description,
        then generates the full JSON-LD passport.

        Pipeline:
            1. analyze_image(image_path) → vision_attrs
            2. merge_inputs(vision_attrs, {"description": description}) → product_data
            3. generate_from_text(product_data) → passport

        Args:
            image_path: Path to the product image (any format Pillow supports).
            description: Natural language product description (any language).

        Returns:
            Full JSON-LD VCDM 2.0 passport dictionary.

        Raises:
            FileNotFoundError: If image_path does not exist.
            ValueError: If the model returns invalid JSON.

        Example:
            >>> gen = DPPGenerator(client)
            >>> passport = gen.generate_from_photo_and_text("bag.jpg", "brand tote")
            >>> print(passport["credentialSubject"]["esprCategory"])
        """
        image_path = Path(image_path)
        # TODO: implement multimodal pipeline
        # from src.core.vision import VisionAnalyzer
        # vision = VisionAnalyzer(self.client)
        # vision_attrs = vision.extract_product_attributes(image_path, description)
        # product_data = self.merge_inputs(vision_attrs, {"description": description})
        # return self.generate_from_text(json.dumps(product_data))
        raise NotImplementedError("DPPGenerator.generate_from_photo_and_text() not yet implemented")

    def merge_inputs(
        self,
        vision_output: dict,
        user_input: dict,
    ) -> dict:
        """Merge vision analysis output with user-provided input.

        Rule: user_input values ALWAYS override vision_output values.
        This prevents the model from overwriting explicitly provided data.

        Args:
            vision_output: Product attributes extracted by VisionAnalyzer.
            user_input: Explicitly provided product data (higher priority).

        Returns:
            Merged dictionary with user_input taking precedence on conflicts.

        Example:
            >>> gen = DPPGenerator(None)
            >>> vision = {"category": "electronics", "materials": ["plastic"]}
            >>> user = {"category": "textiles"}
            >>> merged = gen.merge_inputs(vision, user)
            >>> assert merged["category"] == "textiles"  # user wins
        """
        # Shallow merge: start with vision, overwrite with user
        merged = {**vision_output, **user_input}
        return merged

    def validate(self, passport: dict) -> tuple[bool, list[str]]:
        """Validate a passport dictionary against JSON-LD VCDM 2.0 schema.

        Checks:
          1. Required W3C VC fields present (@context, id, type, issuer, etc.)
          2. credentialSubject has required ESPR fields
          3. JSON-LD structure is expandable (via pyld)
          4. Content hash matches credentialSubject SHA-256

        Args:
            passport: The passport dictionary to validate.

        Returns:
            Tuple of (is_valid: bool, errors: list[str]).
            is_valid is True only if errors list is empty.

        Raises:
            ImportError: If pyld is not installed.

        Example:
            >>> gen = DPPGenerator(client)
            >>> passport = gen.generate_from_text("test product")
            >>> valid, errors = gen.validate(passport)
            >>> print(f"Valid: {valid}, Errors: {errors}")
        """
        errors: list[str] = []

        # Check required W3C VC fields
        required_fields = ["@context", "id", "type", "issuer", "validFrom", "credentialSubject"]
        for field in required_fields:
            if field not in passport:
                errors.append(f"Missing required field: {field}")

        # Check type contains VerifiableCredential
        if "type" in passport:
            if "VerifiableCredential" not in passport.get("type", []):
                errors.append("type must include 'VerifiableCredential'")

        # TODO: validate with pyld (JSON-LD expansion)
        # try:
        #     from pyld import jsonld
        #     expanded = jsonld.expand(passport)
        #     if not expanded:
        #         errors.append("JSON-LD expansion returned empty result")
        # except Exception as e:
        #     errors.append(f"JSON-LD validation error: {e}")

        # TODO: verify content hash
        # if "contentHash" in passport and "credentialSubject" in passport:
        #     expected_hash = self._compute_content_hash(passport["credentialSubject"])
        #     if passport["contentHash"] != f"sha256:{expected_hash}":
        #         errors.append("contentHash does not match credentialSubject SHA-256")

        return len(errors) == 0, errors

    def _build_jsonld_wrapper(
        self,
        credential_subject: dict,
        passport_id: str | None = None,
    ) -> dict:
        """Wrap credentialSubject data in a W3C VCDM 2.0 envelope.

        Args:
            credential_subject: The product data dictionary.
            passport_id: UUID for the passport. Generated if not provided.

        Returns:
            Full JSON-LD passport dictionary.
        """
        if passport_id is None:
            passport_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(days=365 * self.DPP_VALIDITY_YEARS)

        content_hash = self._compute_content_hash(credential_subject)

        return {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://schema.org",
                "https://ref.gs1.org/standards/gs1-jld/contexts/gs1-vocab.jsonld",
            ],
            "id": f"did:web:passportai.example.com:passports:{passport_id}",
            "type": ["VerifiableCredential", "DigitalProductPassport"],
            "issuer": self.ISSUER_DID,
            "validFrom": now.isoformat().replace("+00:00", "Z"),
            "validUntil": valid_until.isoformat().replace("+00:00", "Z"),
            "contentHash": f"sha256:{content_hash}",
            "credentialSubject": credential_subject,
        }

    def _compute_content_hash(self, credential_subject: dict) -> str:
        """Compute SHA-256 hash of credentialSubject with sorted keys.

        Args:
            credential_subject: The credentialSubject dictionary.

        Returns:
            Hex-encoded SHA-256 hash string.

        Note:
            Keys are sorted before hashing to ensure deterministic output.
            This is the canonical hash used in contentHash field.
        """
        canonical = json.dumps(credential_subject, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt template from the prompts directory.

        Args:
            filename: Filename within the prompts/ directory.

        Returns:
            Prompt template as a string.

        Raises:
            FileNotFoundError: If the prompt file does not exist.
        """
        prompt_path = self.prompts_dir / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _parse_llm_json(self, raw: str) -> dict:
        """Parse JSON from LLM response, stripping markdown code blocks.

        Args:
            raw: Raw string response from Gemma model.

        Returns:
            Parsed Python dictionary.

        Raises:
            ValueError: If valid JSON cannot be extracted.
        """
        # Strip markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last line (``` delimiters)
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw[:200]}") from e


if __name__ == "__main__":
    # Test merge_inputs (no Ollama needed)
    gen = DPPGenerator(None)
    vision = {"category": "electronics", "materials": ["ABS plastic"], "colors": ["black"]}
    user = {"category": "textiles", "description": "Tote bag"}
    merged = gen.merge_inputs(vision, user)
    assert merged["category"] == "textiles", "user_input must override vision_output"
    print("merge_inputs OK:", merged)

    # Test _compute_content_hash
    test_subject = {"productName": "Test", "esprCategory": "textiles"}
    hash1 = gen._compute_content_hash(test_subject)
    hash2 = gen._compute_content_hash({"esprCategory": "textiles", "productName": "Test"})
    assert hash1 == hash2, "Hash must be deterministic regardless of key order"
    print(f"content hash OK: sha256:{hash1[:16]}...")
