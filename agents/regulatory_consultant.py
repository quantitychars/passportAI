"""
agents/regulatory_consultant.py — ESPR Regulatory Consultant Agent

Classifies a product into an ESPR category and returns:
  - espr_category: textiles | batteries | electronics | furniture | footwear | chemicals
  - required_fields: list of DPP fields mandatory for this category
  - deadlines: ESPR implementation deadlines for this category
  - applicable_regulations: list of EU regulations

Prompt file: prompts/regulatory_classification.txt

Usage:
    from agents.regulatory_consultant import RegulatoryConsultantAgent
    agent = RegulatoryConsultantAgent(gemma_client)
    result = agent.run(
        product_name="Brand Tote Bag",
        description="100% cotton, made in Ukraine",
        photo_attributes={"category": "textiles", "materials": ["cotton"]},
    )
    # result["espr_category"] == "textiles"
"""

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


class RegulatoryConsultantAgent(BaseAgent):
    """ESPR regulatory classification agent.

    Determines the applicable ESPR category and regulatory requirements
    for a given product.

    Output schema:
        {
            "espr_category": "textiles",
            "required_fields": ["materialComposition", "recycledContent", ...],
            "deadlines": {"mandatory_dpp": "2027-01-01", "mandatory_repair_info": "2028-01-01"},
            "applicable_regulations": ["ESPR 2024/1781", "EU Textile Labelling Regulation"],
            "confidence": 0.92,
            "reasoning": "Product is a textile accessory (tote bag) made from cotton..."
        }
    """

    PROMPT_FILE = "regulatory_classification.txt"

    # ESPR categories with expected DPP deadlines
    CATEGORY_DEADLINES = {
        "textiles": {"mandatory_dpp": "2027-01-01"},
        "electronics": {"mandatory_dpp": "2026-01-01"},
        "batteries": {"mandatory_dpp": "2026-02-18"},
        "furniture": {"mandatory_dpp": "2027-01-01"},
        "footwear": {"mandatory_dpp": "2027-01-01"},
        "chemicals": {"mandatory_dpp": "2028-01-01"},
    }

    def __init__(
        self,
        client: Any,
        prompts_dir: Path | None = None,
    ) -> None:
        """Initialize RegulatoryConsultantAgent.

        Args:
            client: GemmaClient instance.
            prompts_dir: Path to prompts directory.
        """
        super().__init__(client, prompts_dir, name="RegulatoryConsultant")

    def run(
        self,
        product_name: str = "",
        description: str = "",
        photo_attributes: dict | None = None,
        **kwargs,
    ) -> dict:
        """Classify product into ESPR category and determine requirements.

        Args:
            product_name: Product name string.
            description: Product description text.
            photo_attributes: Vision analysis output (optional, improves accuracy).

        Returns:
            Dictionary with espr_category, required_fields, deadlines,
            applicable_regulations, confidence, reasoning.

        Raises:
            ValueError: If model returns invalid JSON.
            RuntimeError: If GemmaClient fails.

        Example:
            >>> agent = RegulatoryConsultantAgent(client)
            >>> result = agent.run(product_name="Tote Bag", description="100% cotton")
            >>> assert result["espr_category"] == "textiles"
        """
        photo_attributes = photo_attributes or {}

        # TODO: implement regulatory classification
        # prompt_template = self._load_prompt(self.PROMPT_FILE)
        # prompt = prompt_template.format(
        #     product_name=product_name,
        #     description=description,
        #     photo_category=photo_attributes.get("category", "unknown"),
        #     photo_materials=", ".join(photo_attributes.get("materials", [])),
        # )
        # result = self._safe_generate(prompt)
        # # Add deadlines from our lookup table
        # category = result.get("espr_category", "unknown")
        # result["deadlines"] = self.CATEGORY_DEADLINES.get(category, {})
        # return result
        raise NotImplementedError("RegulatoryConsultantAgent.run() not yet implemented")

    def get_required_fields(self, espr_category: str) -> list[str]:
        """Return the required DPP fields for an ESPR category.

        Args:
            espr_category: Category string (e.g., "textiles").

        Returns:
            List of required field names for this category.
        """
        # TODO: implement field lookup from category schema
        # schema_map = {
        #     "textiles": "textile_dpp.json",
        #     "batteries": "battery_dpp.json",
        #     ...
        # }
        raise NotImplementedError("RegulatoryConsultantAgent.get_required_fields() not yet implemented")