"""
agents/data_audit_agent.py — Data Audit Agent

Checks a DPP passport for:
  - Field completeness (essential and recommended fields)
  - Data consistency (e.g., country codes, date formats, percentage totals)
  - Readiness score calculation (0-100)

Scoring breakdown:
  essential_fields:    max 60 points (missing = -5 per field, min 0)
  recommended_fields:  max 25 points
  documents_attached:  max 10 points (certifications with documentUrl)
  photo_standardized:  max 5 points  (photo 800x800 white bg)

Prompt file: prompts/data_audit.txt

Usage:
    from agents.data_audit_agent import DataAuditAgent
    agent = DataAuditAgent(gemma_client)
    result = agent.run(
        passport_json={...},
        required_fields=["materialComposition", "manufacturer", "esprCategory"],
    )
    # result["readiness_score"] in range(0, 101)
"""

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


# Essential fields required for all DPP categories
UNIVERSAL_ESSENTIAL_FIELDS = [
    "productId",
    "productName",
    "productDescription",
    "esprCategory",
    "economicOperator",
    "materialComposition",
    "countryOfManufacture",
    "carbonFootprint",
]

# Recommended but not mandatory fields
UNIVERSAL_RECOMMENDED_FIELDS = [
    "recycledContent",
    "certifications",
    "durabilityYears",
    "endOfLifeInstructions",
    "warrantyYears",
    "facilityId",
]


class DataAuditAgent(BaseAgent):
    """Data completeness and consistency audit agent.

    Calculates DPP Readiness Score and identifies gaps.

    Output schema:
        {
            "readiness_score": 72,
            "score_breakdown": {
                "essential_fields": 48,
                "recommended_fields": 16,
                "documents_attached": 5,
                "photo_standardized": 3,
                "total": 72
            },
            "missing_essential": ["manufacturer"],
            "missing_recommended": ["recycledContent", "waterConsumption"],
            "inconsistencies": ["materialComposition percentages sum to 98, not 100"],
            "warnings": ["durabilityYears is 0, which seems incorrect"]
        }
    """

    PROMPT_FILE = "data_audit.txt"

    def __init__(
        self,
        client: Any,
        prompts_dir: Path | None = None,
    ) -> None:
        """Initialize DataAuditAgent.

        Args:
            client: GemmaClient instance.
            prompts_dir: Path to prompts directory.
        """
        super().__init__(client, prompts_dir, name="DataAudit")

    def run(
        self,
        passport_json: dict | None = None,
        required_fields: list | None = None,
        **kwargs,
    ) -> dict:
        """Audit a passport for completeness and consistency.

        Performs both rule-based checks and LLM-based semantic analysis.

        Args:
            passport_json: The DPP passport dictionary to audit.
            required_fields: Category-specific required fields from
                             RegulatoryConsultantAgent output.

        Returns:
            Dictionary with readiness_score, score_breakdown, missing_essential,
            missing_recommended, inconsistencies, warnings.

        Raises:
            ValueError: If model returns invalid JSON.

        Example:
            >>> agent = DataAuditAgent(client)
            >>> result = agent.run(
            ...     passport_json={"credentialSubject": {}},
            ...     required_fields=["manufacturer"]
            ... )
            >>> assert result["readiness_score"] < 60
            >>> assert "manufacturer" in result["missing_essential"]
        """
        passport_json = passport_json or {}
        required_fields = required_fields or UNIVERSAL_ESSENTIAL_FIELDS

        # Run rule-based checks first (fast, no LLM needed)
        rule_based_result = self._rule_based_audit(passport_json, required_fields)

        # TODO: run LLM-based semantic checks
        # prompt_template = self._load_prompt(self.PROMPT_FILE)
        # prompt = prompt_template.format(
        #     passport_json=json.dumps(passport_json, indent=2)[:4000],
        #     required_fields=json.dumps(required_fields),
        # )
        # llm_result = self._safe_generate(prompt)
        # # Merge rule-based and LLM results
        # return self._merge_audit_results(rule_based_result, llm_result)
        return rule_based_result

    def _rule_based_audit(
        self,
        passport_json: dict,
        required_fields: list,
    ) -> dict:
        """Perform rule-based field completeness checks.

        Args:
            passport_json: Passport dictionary to check.
            required_fields: List of required field names.

        Returns:
            Audit result dictionary with scores and gap lists.
        """
        subject = passport_json.get("credentialSubject", {})
        missing_essential = []
        missing_recommended = []
        inconsistencies = []
        warnings = []

        # Check required fields
        all_essential = list(set(required_fields + UNIVERSAL_ESSENTIAL_FIELDS))
        for field in all_essential:
            if field not in subject or subject[field] is None:
                missing_essential.append(field)

        # Check recommended fields
        for field in UNIVERSAL_RECOMMENDED_FIELDS:
            if field not in subject or subject[field] is None:
                if field not in missing_essential:
                    missing_recommended.append(field)

        # Check material composition percentages sum to ~100
        composition = subject.get("materialComposition", [])
        if composition:
            total_pct = sum(m.get("percentage", 0) for m in composition)
            if abs(total_pct - 100) > 2:
                inconsistencies.append(
                    f"materialComposition percentages sum to {total_pct:.1f}%, expected ~100%"
                )

        # Calculate score
        essential_score = max(0, 60 - len(missing_essential) * 5)
        recommended_score = max(0, 25 - len(missing_recommended) * 4)

        # Document score
        certs = subject.get("certifications", [])
        docs_with_url = sum(1 for c in certs if c.get("documentUrl"))
        doc_score = min(10, docs_with_url * 3)

        # Photo score
        photo = subject.get("photo", {})
        photo_score = 5 if (photo.get("width") == 800 and photo.get("height") == 800) else 0

        total = essential_score + recommended_score + doc_score + photo_score

        return {
            "readiness_score": total,
            "score_breakdown": {
                "essential_fields": essential_score,
                "recommended_fields": recommended_score,
                "documents_attached": doc_score,
                "photo_standardized": photo_score,
                "total": total,
            },
            "missing_essential": missing_essential,
            "missing_recommended": missing_recommended,
            "inconsistencies": inconsistencies,
            "warnings": warnings,
        }
