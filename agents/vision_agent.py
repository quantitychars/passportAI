# agents/vision_agent.py

class VisionAgent(BaseAgent):
    """Extracts structured product attributes from product images.
    
    Output schema:
        {
            "category": "textiles",
            "materials": ["cotton", "polyester"],
            "colors": ["natural", "beige"],
            "certifications_visible": ["GOTS label"],
            "special_markings": ["Made in Ukraine"],
            "confidence_visual": 0.85
        }
    """
    def run(self, image_path: str, description: str = "") -> dict:
        # Шаг 1: analyze_image (стандартный)
        image_description = self.client.analyze_image(
            image_path,
            "Describe ALL visible details: materials, labels, markings, care instructions, country of origin, barcodes, certifications"
        )
        
        # ШАГ 2 (НОВЫЙ): Vision-specific think()
        # Gemma 4 видит изображение + думает о нём одновременно
        vision_reasoning = self.client.think(
            f"""
Image shows: {image_description}
User says product is: {description}

Think about:
1. Do the visual details CONFIRM or CONTRADICT the user description?
2. What materials are CERTAIN vs GUESSED from the image?
3. Are there any certifications/labels visible? What do they mean for ESPR?
4. What is DEFINITELY missing that a DPP requires?
"""
        )
        
        # Шаг 3: extract structured output with reasoning context
        combined = f"Visual facts: {image_description}\nReasoning: {vision_reasoning}\nUser: {description}"
        return self.call_tool(combined, VISION_TOOL, VISION_SYSTEM)