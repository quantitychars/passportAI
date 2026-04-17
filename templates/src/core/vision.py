"""
src/core/vision.py — Vision Analysis Module

Extracts structured product attributes from images using Gemma 4's
multimodal capabilities via GemmaClient.analyze_image().

Output schema:
    {
        "category": "textiles",
        "materials": ["cotton", "polyester"],
        "colors": ["natural", "beige"],
        "dimensions_estimate": {"width_cm": 38, "height_cm": 42},
        "certifications_visible": ["GOTS label"],
        "special_markings": ["Made in Ukraine", "care symbols"]
    }

Usage:
    from src.core.vision import VisionAnalyzer
    analyzer = VisionAnalyzer(gemma_client)
    attrs = analyzer.extract_product_attributes("photo.jpg", "cotton tote bag")
"""

from pathlib import Path
from typing import Any


class VisionAnalyzer:
    """Extracts product attributes from images using Gemma 4 vision.

    Attributes:
        client: GemmaClient instance for multimodal inference.
        prompt_path: Path to vision_analysis.txt prompt template.
    """

    def __init__(
        self,
        client: Any,  # GemmaClient
        prompt_path: Path | None = None,
    ) -> None:
        """Initialize VisionAnalyzer.

        Args:
            client: GemmaClient instance with analyze_image() support.
            prompt_path: Path to vision prompt file. Defaults to prompts/vision_analysis.txt.
        """
        self.client = client
        self.prompt_path = prompt_path or Path("prompts/vision_analysis.txt")
        # TODO: load prompt template
        # self._prompt_template = self.prompt_path.read_text()

    def extract_product_attributes(
        self,
        image_path: str | Path,
        description: str = "",
    ) -> dict:
        """Extract product attributes from a product photo.

        Sends the image to Gemma 4 with the vision analysis prompt.
        Returns structured JSON with category, materials, colors, etc.

        Args:
            image_path: Path to the product image.
            description: Optional user-provided description to guide analysis.
                         If provided, the model uses it as context.

        Returns:
            Dictionary with keys:
                - category (str): ESPR product category
                - materials (list[str]): Visible materials
                - colors (list[str]): Product colors
                - dimensions_estimate (dict): Estimated width/height in cm
                - certifications_visible (list[str]): Labels/marks visible in image
                - special_markings (list[str]): Other markings (country of origin, etc.)

        Raises:
            FileNotFoundError: If image does not exist.
            ValueError: If model returns invalid JSON.

        Example:
            >>> analyzer = VisionAnalyzer(client)
            >>> attrs = analyzer.extract_product_attributes("brand_bag.jpg")
            >>> print(attrs["category"])  # "textiles"
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # TODO: implement vision analysis
        # prompt = self._build_prompt(description)
        # raw = self.client.analyze_image(image_path, prompt)
        # return self._parse_attributes(raw)
        raise NotImplementedError("VisionAnalyzer.extract_product_attributes() not yet implemented")

    def _build_prompt(self, user_description: str = "") -> str:
        """Build the vision analysis prompt with optional user context.

        Args:
            user_description: User's product description to include as context.

        Returns:
            Formatted prompt string ready for GemmaClient.analyze_image().
        """
        # TODO: implement prompt building with template substitution
        # context_section = f"\nUser description: {user_description}" if user_description else ""
        # return self._prompt_template.replace("[USER_DESCRIPTION]", context_section)
        raise NotImplementedError("VisionAnalyzer._build_prompt() not yet implemented")

    def _parse_attributes(self, raw: str) -> dict:
        """Parse and validate the model's JSON response.

        Args:
            raw: Raw string from GemmaClient.analyze_image().

        Returns:
            Validated attributes dictionary with all required keys.

        Raises:
            ValueError: If JSON cannot be parsed or required keys are missing.
        """
        # TODO: parse JSON, validate schema, fill missing keys with defaults
        # import json
        # text = raw.strip()
        # if "```" in text:
        #     text = text.split("```json")[-1].split("```")[0].strip()
        # data = json.loads(text)
        # # Ensure required keys with defaults
        # return {
        #     "category": data.get("category", "unknown"),
        #     "materials": data.get("materials", []),
        #     "colors": data.get("colors", []),
        #     "dimensions_estimate": data.get("dimensions_estimate", {}),
        #     "certifications_visible": data.get("certifications_visible", []),
        #     "special_markings": data.get("special_markings", []),
        # }
        raise NotImplementedError("VisionAnalyzer._parse_attributes() not yet implemented")


if __name__ == "__main__":
    print("VisionAnalyzer skeleton loaded OK")
    print("Requires GemmaClient with analyze_image() support")
    print("Test after implementing: python src/core/vision.py")
