"""
src/ui/gradio_app.py — Gradio Web Interface

Provides a user-friendly web UI for generating Digital Product Passports.
Runs on port 7860 (configurable via GRADIO_PORT env var).

Interface layout:
  Left panel (inputs):
    - Image upload (product photo)
    - Product description textbox
    - GTIN barcode (optional)
    - Certificate PDFs upload (optional)
    - Storage mode dropdown (local | s3)
    - Generate button

  Right panel (outputs):
    - Progress bar (13 steps with step names)
    - JSON preview (passport.json)
    - QR code image
    - Download ZIP button

Usage:
    # Standalone (for testing):
    python src/ui/gradio_app.py

    # Via app.py (production):
    from src.ui.gradio_app import build_interface
    interface = build_interface()
    interface.launch(server_port=7860)
"""

import os

# TODO: import Gradio
# import gradio as gr

STEP_NAMES = [
    "1/13 — Input validation",
    "2/13 — Vision analysis",
    "3/13 — Photo standardization",
    "4/13 — Merging inputs",
    "5/13 — Regulatory classification",
    "6/13 — DPP generation",
    "7/13 — Legal compliance check",
    "8/13 — LCA estimation",
    "9/13 — Data audit",
    "10/13 — GS1 product ID",
    "11/13 — Gap report",
    "12/13 — Saving files",
    "13/13 — QR code generation",
]


def build_interface():
    """Build and return the Gradio interface.

    Returns:
        gr.Blocks instance (not launched — caller decides port).

    Raises:
        ImportError: If gradio is not installed.

    Example:
        >>> interface = build_interface()
        >>> interface.launch(server_port=7860)
    """
    # TODO: implement Gradio UI
    # with gr.Blocks(title="PassportAI", theme=gr.themes.Soft()) as interface:
    #     gr.Markdown("# PassportAI\nGenerate ESPR-compliant Digital Product Passports")
    #
    #     with gr.Row():
    #         # Input column
    #         with gr.Column(scale=1):
    #             photo_input = gr.Image(
    #                 type="filepath",
    #                 label="Product Photo",
    #                 sources=["upload", "clipboard"],
    #             )
    #             description_input = gr.Textbox(
    #                 label="Product Description",
    #                 placeholder="e.g. Cotton tote bag, made in Ukraine, GOTS certified",
    #                 lines=3,
    #             )
    #             gtin_input = gr.Textbox(
    #                 label="GTIN Barcode (optional)",
    #                 placeholder="05901234123457",
    #                 max_lines=1,
    #             )
    #             cert_input = gr.File(
    #                 file_types=[".pdf"],
    #                 label="Certificates (optional)",
    #                 file_count="multiple",
    #             )
    #             storage_input = gr.Dropdown(
    #                 choices=["local", "s3"],
    #                 value="local",
    #                 label="Storage Mode",
    #             )
    #             generate_btn = gr.Button("Generate DPP", variant="primary", size="lg")
    #
    #         # Output column
    #         with gr.Column(scale=1):
    #             progress_bar = gr.Textbox(label="Progress", interactive=False)
    #             score_output = gr.Number(label="Readiness Score (0-100)", interactive=False)
    #             json_output = gr.JSON(label="passport.json preview")
    #             qr_output = gr.Image(label="QR Code", type="filepath")
    #             download_btn = gr.File(label="Download ZIP package")
    #             error_output = gr.Textbox(label="Errors", visible=False, interactive=False)
    #
    #     generate_btn.click(
    #         fn=generate_dpp,
    #         inputs=[photo_input, description_input, gtin_input, cert_input, storage_input],
    #         outputs=[progress_bar, score_output, json_output, qr_output, download_btn, error_output],
    #     )
    #
    # return interface
    raise NotImplementedError("build_interface() not yet implemented")


async def generate_dpp(
    photo_path: str,
    description: str,
    gtin: str | None,
    certificates: list | None,
    storage_mode: str,
) -> tuple:
    """Gradio callback: runs the DPP pipeline and streams progress updates.

    Args:
        photo_path: Path to uploaded product photo.
        description: Product description text.
        gtin: Optional GTIN-14 barcode string.
        certificates: List of uploaded certificate PDF paths.
        storage_mode: "local" or "s3".

    Yields:
        Tuples of (progress_text, score, passport_json, qr_path, zip_path, error_text)
        Yielded for each pipeline step to enable live progress updates.

    Note:
        Uses gr.Progress() for step-by-step updates.
        Each yield updates the UI in real time.
    """
    # TODO: implement pipeline orchestration
    # Validate inputs
    if not photo_path:
        yield ("Error: No photo uploaded", None, None, None, None, "Please upload a product photo")
        return
    if not description.strip():
        yield ("Error: No description", None, None, None, None, "Please enter a product description")
        return

    # TODO: call pipeline steps with progress updates
    # for step_num, step_name in enumerate(STEP_NAMES, 1):
    #     yield (step_name, None, None, None, None, "")
    #     # ... execute step
    raise NotImplementedError("generate_dpp() not yet implemented")


def create_zip_package(passport_id: str, output_dir: str = "./output") -> str:
    """Create a ZIP archive of all passport files for download.

    Args:
        passport_id: UUID of the passport.
        output_dir: Base output directory.

    Returns:
        Path to the created ZIP file.

    Raises:
        FileNotFoundError: If the passport directory doesn't exist.
    """
    # TODO: implement ZIP creation
    # import zipfile
    # package_dir = Path(output_dir) / passport_id
    # zip_path = package_dir / "passport_package.zip"
    # with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
    #     for file in package_dir.iterdir():
    #         if file.name != "passport_package.zip":
    #             zf.write(str(file), file.name)
    # return str(zip_path)
    raise NotImplementedError("create_zip_package() not yet implemented")


if __name__ == "__main__":
    port = int(os.getenv("GRADIO_PORT", 7860))
    print(f"Gradio UI skeleton — build_interface() not yet implemented")
    print(f"After implementation, run: python src/ui/gradio_app.py")
    print(f"UI will be at: http://localhost:{port}")
    # TODO: uncomment after implementation
    # interface = build_interface()
    # interface.launch(server_port=port, server_name="0.0.0.0", share=False)
