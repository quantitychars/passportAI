"""
agents/legal_agent.py — Legal Compliance Agent

Checks a DPP draft for legal compliance issues:
  - CE marking requirement (for electronics, machinery, etc.)
  - Declaration of Conformity (DoC) presence
  - REACH SVHC substances (Annex XIV + candidate list)
  - RoHS applicability (electronics)
  - VAT number verification (EU VIES API)

Prompt file: prompts/legal_review.txt

Usage:
    from agents.legal_agent import LegalAgent
    agent = LegalAgent(gemma_client)
    result = agent.run(
        passport_draft={...},
        material_composition=[{"material": "ABS plastic", "percentage": 70}, ...],
        espr_category="electronics",
    )
    # result["reach_flags"] contains flagged substances
"""

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


# REACH SVHC candidate list substances commonly found in consumer products
# Full list: https://echa.europa.eu/candidate-list-table
KNOWN_SVHC_SUBSTANCES = {
    "neodymium", "bisphenol a", "bpa", "dibutyl phthalate", "dbp",
    "lead", "cadmium", "mercury", "arsenic", "chromium vi", "hexavalent chromium",
    "formaldehyde", "nonylphenol", "bisphenol s", "bps", "phthalates",
}


class LegalAgent(BaseAgent):
    """Legal compliance checking agent.

    Analyzes passport draft for regulatory compliance gaps.

    Output schema:
        {
            "ce_required": false,
            "doc_present": false,
            "doc_required": false,
            "reach_flags": ["neodymium (SVHC candidate, REACH Article 33 applies)"],
            "rohs_applicable": false,
            "vat_verified": null,
            "missing_documents": ["OEKO-TEX Standard 100 recommended"],
            "compliance_flags": [],
            "overall_status": "compliant" | "attention_required" | "non_compliant"
        }
    """

    PROMPT_FILE = "legal_review.txt"

    def __init__(
        self,
        client: Any,
        prompts_dir: Path | None = None,
        enable_vies: bool = True,
    ) -> None:
        """Initialize LegalAgent.

        Args:
            client: GemmaClient instance.
            prompts_dir: Path to prompts directory.
            enable_vies: Whether to call the EU VIES API for VAT verification.
                         Set to False for offline use or testing.
        """
        super().__init__(client, prompts_dir, name="LegalAgent")
        self.enable_vies = enable_vies

    def run(
        self,
        passport_draft: dict | None = None,
        material_composition: list | None = None,
        espr_category: str = "unknown",
        **kwargs,
    ) -> dict:
        """Check passport draft for legal compliance issues.

        Args:
            passport_draft: The DPP passport dictionary to check.
            material_composition: List of dicts with "material" and "percentage" keys.
            espr_category: ESPR product category (affects CE/RoHS requirements).

        Returns:
            Dictionary with ce_required, doc_present, reach_flags, rohs_applicable,
            missing_documents, compliance_flags, overall_status.

        Raises:
            ValueError: If model returns invalid JSON.

        Example:
            >>> agent = LegalAgent(client)
            >>> result = agent.run(
            ...     material_composition=[{"material": "neodymium", "percentage": 5}],
            ...     espr_category="electronics"
            ... )
            >>> assert "neodymium" in str(result["reach_flags"])
        """
        passport_draft = passport_draft or {}
        material_composition = material_composition or []

        # Pre-check: quick SVHC scan before LLM call
        quick_flags = self._quick_svhc_scan(material_composition)

        # TODO: implement full LLM-based legal review
        # prompt_template = self._load_prompt(self.PROMPT_FILE)
        # prompt = prompt_template.format(
        #     passport_json=json.dumps(passport_draft, indent=2)[:3000],
        #     materials=json.dumps(material_composition),
        #     espr_category=espr_category,
        # )
        # result = self._safe_generate(prompt)
        # result["reach_flags"] = list(set(result.get("reach_flags", []) + quick_flags))
        #
        # # VAT verification
        # if self.enable_vies and passport_draft.get("credentialSubject", {}).get("economicOperator", {}).get("vatNumber"):
        #     vat = passport_draft["credentialSubject"]["economicOperator"]["vatNumber"]
        #     result["vat_verified"] = self._verify_vat(vat)
        #
        # return result
        raise NotImplementedError("LegalAgent.run() not yet implemented")

    def _quick_svhc_scan(self, material_composition: list) -> list[str]:
        """Quick rule-based SVHC check without LLM.

        Checks material names against known SVHC substances list.
        The LLM check is more thorough — this is a fast pre-filter.

        Args:
            material_composition: List of {"material": str, "percentage": float} dicts.

        Returns:
            List of SVHC flag strings for detected substances.

        Example:
            >>> agent = LegalAgent(None)
            >>> flags = agent._quick_svhc_scan([{"material": "neodymium", "percentage": 5}])
            >>> assert len(flags) > 0
        """
        flags = []
        for entry in material_composition:
            material_lower = entry.get("material", "").lower()
            for svhc in KNOWN_SVHC_SUBSTANCES:
                if svhc in material_lower:
                    pct = entry.get("percentage", 0)
                    flags.append(
                        f"{entry['material']} ({pct}%) — SVHC candidate. "
                        f"REACH Article 33 disclosure required if >0.1% w/w."
                    )
                    break
        return flags

    def _verify_vat(self, vat_number: str) -> bool | None:
        """Verify VAT number against EU VIES API.

        Only works for EU-registered legal entities.
        Returns None for non-EU VAT numbers (e.g., UA prefix).

        Args:
            vat_number: VAT number string (e.g., "DE123456789").

        Returns:
            True if VAT is valid, False if invalid, None if non-EU or API unavailable.
        """
        # TODO: implement VIES SOAP call
        # if not vat_number.startswith(tuple(EU_COUNTRY_CODES)):
        #     return None  # Non-EU VAT — skip VIES
        # try:
        #     from zeep import Client
        #     client = Client(VIES_API_URL)
        #     country_code = vat_number[:2]
        #     number = vat_number[2:]
        #     result = client.service.checkVat(countryCode=country_code, vatNumber=number)
        #     return result.valid
        # except Exception:
        #     return None  # VIES unavailable — don't fail the pipeline
        raise NotImplementedError("LegalAgent._verify_vat() not yet implemented")
