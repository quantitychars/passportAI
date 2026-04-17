"""
src/core/gap_report.py — Compliance Gap Report Generator

Generates a PDF gap report from:
  - Data Audit Agent results (readiness_score, missing fields)
  - Legal Agent results (compliance flags, missing documents)
  - The full passport JSON (for context)

Output: gap_report.pdf in the passport's output directory.

The report includes:
  - Overall readiness score (0-100) with visual gauge
  - Critical gaps (missing essential fields)
  - Legal compliance flags (REACH, RoHS, CE marking)
  - Recommended actions with ESPR deadlines
  - Field-by-field completion checklist

Usage:
    from src.core.gap_report import GapReportGenerator
    gen = GapReportGenerator(gemma_client)
    pdf_path = gen.generate(audit_result, legal_result, passport_json, output_dir)
"""

from pathlib import Path
from typing import Any


class GapReportGenerator:
    """Generates PDF compliance gap reports using Jinja2 + WeasyPrint.

    Attributes:
        client: GemmaClient instance for generating action recommendations.
        template_path: Path to gap_report.html.jinja2 template.
        prompt_path: Path to gap_check.txt prompt.
    """

    def __init__(
        self,
        client: Any,  # GemmaClient — can be None if using pre-computed gaps
        template_path: Path | None = None,
        prompt_path: Path | None = None,
    ) -> None:
        """Initialize GapReportGenerator.

        Args:
            client: GemmaClient instance for LLM-based gap analysis.
                    Can be None if audit_result and legal_result are pre-computed.
            template_path: Path to Jinja2 HTML template.
            prompt_path: Path to gap check prompt.
        """
        self.client = client
        self.template_path = template_path or Path("templates/gap_report.html.jinja2")
        self.prompt_path = prompt_path or Path("prompts/gap_check.txt")

    def generate(
        self,
        audit_result: dict,
        legal_result: dict,
        passport_json: dict,
        output_dir: Path | None = None,
    ) -> Path:
        """Generate a PDF gap report.

        Renders the Jinja2 HTML template with gap data, then converts to PDF
        using WeasyPrint.

        Args:
            audit_result: Output from DataAuditAgent.run() containing
                          readiness_score, missing_essential, missing_recommended,
                          inconsistencies, warnings.
            legal_result: Output from LegalAgent.run() containing
                          compliance_flags, missing_documents, reach_flags.
            passport_json: The full passport dictionary (for product name, etc.).
            output_dir: Directory to save gap_report.pdf. Defaults to current dir.

        Returns:
            Path to the generated gap_report.pdf file.

        Raises:
            ImportError: If jinja2 or weasyprint is not installed.
            FileNotFoundError: If template file does not exist.

        Example:
            >>> gen = GapReportGenerator(client)
            >>> pdf = gen.generate(audit, legal, passport, output_dir=Path("output/uuid"))
            >>> print(pdf.stat().st_size)  # Should be > 10000 bytes
        """
        if output_dir is None:
            output_dir = Path(".")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # TODO: implement PDF generation
        # context = self._build_template_context(audit_result, legal_result, passport_json)
        # html_content = self._render_template(context)
        # pdf_path = output_dir / "gap_report.pdf"
        # self._html_to_pdf(html_content, pdf_path)
        # return pdf_path
        raise NotImplementedError("GapReportGenerator.generate() not yet implemented")

    def analyze_gaps(
        self,
        passport_json: dict,
        required_fields: list[str],
    ) -> dict:
        """Use Gemma 4 to analyze gaps in a passport and generate recommendations.

        Args:
            passport_json: The passport to analyze.
            required_fields: List of field names required for the product's ESPR category.

        Returns:
            Dictionary with:
                - critical_gaps (list[str]): Fields that must be filled before EU market
                - recommended_actions (list[dict]): Each action has field, priority, deadline, how_to
                - estimated_effort_hours (int): Rough estimate to complete all gaps

        Raises:
            RuntimeError: If Gemma client is not set (client=None).
        """
        if self.client is None:
            raise RuntimeError("GemmaClient required for analyze_gaps(). Pass client= to constructor.")

        # TODO: implement LLM-based gap analysis
        # prompt = self._build_gap_prompt(passport_json, required_fields)
        # raw = self.client.generate(prompt)
        # return self._parse_gap_response(raw)
        raise NotImplementedError("GapReportGenerator.analyze_gaps() not yet implemented")

    def _build_template_context(
        self,
        audit_result: dict,
        legal_result: dict,
        passport_json: dict,
    ) -> dict:
        """Build the Jinja2 template context dictionary.

        Args:
            audit_result: Data audit agent output.
            legal_result: Legal agent output.
            passport_json: Full passport dictionary.

        Returns:
            Template context dict with all variables needed by gap_report.html.jinja2.
        """
        # TODO: extract relevant fields for template rendering
        raise NotImplementedError("GapReportGenerator._build_template_context() not yet implemented")

    def _render_template(self, context: dict) -> str:
        """Render the HTML gap report template.

        Args:
            context: Template variables dictionary.

        Returns:
            Rendered HTML string.
        """
        # TODO: implement Jinja2 template rendering
        # from jinja2 import Environment, FileSystemLoader
        # env = Environment(loader=FileSystemLoader(str(self.template_path.parent)))
        # template = env.get_template(self.template_path.name)
        # return template.render(**context)
        raise NotImplementedError("GapReportGenerator._render_template() not yet implemented")

    def _html_to_pdf(self, html_content: str, output_path: Path) -> None:
        """Convert HTML string to PDF using WeasyPrint.

        Args:
            html_content: Rendered HTML string.
            output_path: Target path for the PDF file.

        Raises:
            ImportError: If weasyprint is not installed.
        """
        # TODO: implement HTML → PDF conversion
        # try:
        #     from weasyprint import HTML
        #     HTML(string=html_content).write_pdf(str(output_path))
        # except ImportError:
        #     raise ImportError("weasyprint not installed. Run: pip install weasyprint")
        raise NotImplementedError("GapReportGenerator._html_to_pdf() not yet implemented")


if __name__ == "__main__":
    print("GapReportGenerator skeleton loaded OK")
