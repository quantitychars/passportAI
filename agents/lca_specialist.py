"""
agents/lca_specialist.py — LCA (Life Cycle Assessment) Specialist Agent

Estimates the Global Warming Potential (GWP) carbon footprint from:
  - Material composition (type and percentage)
  - Country of manufacture (affects energy grid carbon intensity)
  - Product weight (if provided)

Uses ecoinvent 3.9 proxy factors for estimation.
Low confidence (<0.7) indicates need for proper LCA study.

Prompt file: prompts/lca_assessment.txt

Usage:
    from agents.lca_specialist import LCASpecialistAgent
    agent = LCASpecialistAgent(gemma_client)
    result = agent.run(
        material_composition=[{"material": "cotton", "percentage": 100}],
        country_of_manufacture="UA",
    )
    # result["gwp_kg_co2e"] ~= 3.2, result["confidence"] < 0.7
"""

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


# Carbon intensity of electricity grids (kg CO2e/kWh) — IEA 2022
GRID_CARBON_INTENSITY = {
    "UA": 0.31,   # Ukraine (mixed: nuclear + thermal)
    "DE": 0.38,   # Germany
    "PL": 0.76,   # Poland (coal-heavy)
    "FR": 0.06,   # France (nuclear-dominant)
    "CN": 0.62,   # China
    "IN": 0.71,   # India
    "US": 0.37,   # USA average
    "BD": 0.65,   # Bangladesh (major textile producer)
    "TR": 0.43,   # Turkey
}

DEFAULT_GRID_INTENSITY = 0.45  # Global average


class LCASpecialistAgent(BaseAgent):
    """LCA and carbon footprint estimation agent.

    Provides GWP estimates using proxy factors when primary LCA data
    is not available. All estimates should be validated by a proper
    ISO 14040/14044 LCA study for regulatory compliance.

    Output schema:
        {
            "gwp_kg_co2e": 3.2,
            "confidence": 0.55,
            "scope": "cradle-to-gate",
            "methodology": "Estimated using ecoinvent 3.9 proxy factors...",
            "data_source": "PassportAI LCA Specialist Agent v1.0",
            "breakdown": {
                "raw_materials": 2.1,
                "manufacturing": 0.8,
                "packaging": 0.3
            },
            "recommendation": "Commission full LCA study for Level 3 compliance"
        }
    """

    PROMPT_FILE = "lca_assessment.txt"

    def __init__(
        self,
        client: Any,
        prompts_dir: Path | None = None,
    ) -> None:
        """Initialize LCASpecialistAgent.

        Args:
            client: GemmaClient instance.
            prompts_dir: Path to prompts directory.
        """
        super().__init__(client, prompts_dir, name="LCASpecialist")

    def run(
        self,
        material_composition: list | None = None,
        country_of_manufacture: str = "unknown",
        product_weight_kg: float | None = None,
        **kwargs,
    ) -> dict:
        """Estimate GWP carbon footprint from material composition.

        Args:
            material_composition: List of {"material": str, "percentage": float} dicts.
            country_of_manufacture: ISO 3166-1 alpha-2 country code (e.g., "UA").
            product_weight_kg: Product weight in kilograms (improves accuracy).

        Returns:
            Dictionary with gwp_kg_co2e, confidence, scope, methodology,
            data_source, breakdown, recommendation.

        Raises:
            ValueError: If model returns invalid JSON.

        Example:
            >>> agent = LCASpecialistAgent(client)
            >>> result = agent.run(
            ...     material_composition=[{"material": "cotton", "percentage": 100}],
            ...     country_of_manufacture="UA"
            ... )
            >>> assert result["confidence"] < 0.7  # Low confidence without primary data
        """
        material_composition = material_composition or []
        grid_intensity = GRID_CARBON_INTENSITY.get(
            country_of_manufacture.upper(), DEFAULT_GRID_INTENSITY
        )

        # TODO: implement LLM-based LCA estimation
        # prompt_template = self._load_prompt(self.PROMPT_FILE)
        # prompt = prompt_template.format(
        #     materials=json.dumps(material_composition),
        #     country=country_of_manufacture,
        #     grid_intensity=grid_intensity,
        #     weight_kg=product_weight_kg or "unknown",
        # )
        # result = self._safe_generate(prompt)
        # result["data_source"] = "PassportAI LCA Specialist Agent v1.0"
        # return result
        raise NotImplementedError("LCASpecialistAgent.run() not yet implemented")

    def get_grid_intensity(self, country_code: str) -> float:
        """Get electricity grid carbon intensity for a country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code.

        Returns:
            Carbon intensity in kg CO2e/kWh.
            Returns DEFAULT_GRID_INTENSITY if country not in database.
        """
        return GRID_CARBON_INTENSITY.get(country_code.upper(), DEFAULT_GRID_INTENSITY)
