from __future__ import annotations

import html
import json
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import gradio as gr
except ImportError:  # pragma: no cover - exercised only in incomplete installs
    gr = None  # type: ignore[assignment]

from agents.data_audit_agent import DataAuditAgent
from agents.gs1_specialist import GS1Specialist
from agents.lca_specialist import LCASpecialist
from agents.legal_agent import LegalAgent
from agents.regulatory_consultant import RegulatoryConsultant
from agents.vision_agent import VisionAgent
from src.core.dpp_generator import DPPGenerator
from src.core.gap_report import GapReportGenerator
from src.core.gemma_client import GemmaClient
from src.core.passport_renderer import PassportRenderer
from src.core.pipeline import PassportPipeline
from src.core.qr_generator import QRCodeGenerator
from src.storage.aws_s3 import S3Storage
from src.storage.local import LocalStorage

SUPPORTED_PRODUCT_GROUPS = ["batteries", "electrical_appliances", "textiles"]
RUNTIME_MODES = ["demo_mock", "live_gemma"]
STORAGE_MODES = ["local", "s3"]

PROGRESS_EVENTS = [
    "Preparing product input",
    "Packaging product image",
    "Running visual product analysis",
    "Classifying regulatory product group",
    "Checking legal evidence",
    "Checking sustainability evidence",
    "Checking identifiers and resolver readiness",
    "Synthesizing audit result",
    "Generating passport.json",
    "Rendering passport.html",
    "Rendering gap_report.html",
    "Generating qr.png",
    "Uploading artifacts to storage",
    "Finalizing package",
]

EMPTY_STATE_GUIDANCE = """
<div class=\"pa-empty\">
  <h2>Create a Digital Product Passport</h2>
  <p>Upload a product photo, add product basics, and generate a passport package.</p>
  <div class=\"pa-empty-grid\">
    <section>
      <h3>How to ask</h3>
      <ul>
        <li>Create a battery passport from this product photo.</li>
        <li>Analyze this textile product and generate a gap report.</li>
        <li>Generate a draft passport and tell me what is missing for publication.</li>
      </ul>
    </section>
    <section>
      <h3>What you can provide</h3>
      <ul>
        <li>Product photo, group, brand, and description.</li>
        <li>Identifiers such as GTIN or operator ID.</li>
        <li>Supplier evidence and technical documentation references.</li>
      </ul>
    </section>
    <section>
      <h3>What PassportAI generates</h3>
      <ul>
        <li>passport.html</li>
        <li>passport.json</li>
        <li>gap_report.html</li>
        <li>qr.png</li>
      </ul>
    </section>
  </div>
</div>
"""


@dataclass(frozen=True)
class S3UIConfig:
    region: str = ""
    bucket: str = ""
    prefix: str = "passports"
    public_base_url: str = ""
    endpoint_url: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""


@dataclass
class UIRunView:
    success: bool
    messages: list[tuple[str, str]] = field(default_factory=list)
    progress_html: str = ""
    passport_preview_html: str = ""
    gap_report_preview_html: str = ""
    passport_json: dict[str, Any] | None = None
    qr_path: str | None = None
    run_summary_markdown: str = ""
    actions_html: str = ""
    zip_path: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


class DemoVisionAgent:
    """Deterministic fixture vision agent for UI development/demo mode.

    This is explicitly not a production evidence source. It exists so the UI can
    be tested when local Gemma/Ollama cannot load the vision model.
    """

    agent_name = "VisionAgent"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        product_group = _normalize_product_group(
            kwargs.get("product_group_hint") or "batteries"
        )
        image_url = str(kwargs.get("image_url") or "")
        description = str(kwargs.get("description") or "")

        if product_group not in SUPPORTED_PRODUCT_GROUPS:
            product_group = "batteries"

        names = {
            "batteries": "Demo battery product",
            "electrical_appliances": "Demo electrical appliance",
            "textiles": "Demo textile product",
        }

        sectoral: dict[str, Any] = {
            "batteries": None,
            "electrical_appliances": None,
            "textiles": None,
        }

        if product_group == "batteries":
            sectoral["batteries"] = {
                "battery_category_hint": "portable",
                "chemistry_visual_hint": "unknown",
            }
        elif product_group == "electrical_appliances":
            sectoral["electrical_appliances"] = {
                "visible_power_interface": "unknown",
            }
        else:
            sectoral["textiles"] = {
                "material_visual_hint": "unknown textile material",
            }

        payload = {
            "domain_data": {
                "espr_core": {
                    "product_group_hint": product_group,
                    "product_name": names[product_group],
                    "product_description": description or names[product_group],
                    "product_image_url": image_url,
                    "visible_certifications": [],
                    "visible_markings": [],
                    "visible_warnings": [],
                },
                "sectoral": sectoral,
            },
            "assessment": {
                "confidence_source": "insufficient_data",
                "confidence_score": 0.45,
                "missing_fields": [],
                "warnings": [
                    "Demo mode uses fixture vision output; live Gemma was not called."
                ],
                "assumptions": [],
                "contradictions": [],
                "needs_human_review": True,
            },
            "advisory": {
                "agent_summary": "Demo vision fixture produced bounded visible-evidence hints.",
                "business_risks": [],
                "recommended_next_actions": [],
                "supplier_requests": [],
                "where_to_get_data": [],
                "next_batch_improvements": [],
            },
        }

        return {
            "success": True,
            "data": payload,
            "agent": "VisionAgent",
            "is_mock": True,
        }


def _normalize_product_group(value: Any) -> str:
    return str(value or "").strip().lower()


def validate_runtime_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in RUNTIME_MODES:
        raise ValueError(
            f"Unsupported runtime mode {value!r}. Expected one of: {', '.join(RUNTIME_MODES)}."
        )
    return normalized


def validate_storage_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in STORAGE_MODES:
        raise ValueError(
            f"Unsupported storage mode {value!r}. Expected one of: {', '.join(STORAGE_MODES)}."
        )
    return normalized


def validate_minimum_inputs(
    *,
    image_path: str | Path | None,
    product_group: str,
    brand_name: str,
    description: str,
) -> list[str]:
    errors: list[str] = []

    if not image_path:
        errors.append("Upload a product photo before generating a passport.")
    elif not Path(image_path).exists():
        errors.append(f"Uploaded product photo does not exist: {image_path}")

    if _normalize_product_group(product_group) not in SUPPORTED_PRODUCT_GROUPS:
        errors.append("Choose a supported product group.")

    if not str(brand_name or "").strip():
        errors.append("Brand name is required for the demo passport.")

    if not str(description or "").strip():
        errors.append("Product description is required.")

    return errors


def build_initial_ui_state() -> dict[str, Any]:
    return {
        "has_started": False,
        "is_running": False,
        "runtime_mode": "demo_mock",
        "storage_mode": "local",
        "latest_input": {},
        "latest_result": None,
        "artifact_paths": {},
        "artifact_urls": {},
        "messages": [],
        "progress_events": [],
        "errors": [],
        "warnings": [],
    }


def build_initial_action_state() -> dict[str, bool]:
    return {
        "open_passport": False,
        "open_gap_report": False,
        "download_json": False,
        "download_zip": False,
        "open_public_url": False,
        "push_to_s3": False,
        "generate_qr": False,
    }


def build_action_state(result: Any | None) -> dict[str, bool]:
    if result is None or not getattr(result, "success", False):
        return build_initial_action_state()

    artifact_paths = getattr(result, "artifact_paths", {}) or {}
    return {
        "open_passport": "passport.html" in artifact_paths,
        "open_gap_report": "gap_report.html" in artifact_paths,
        "download_json": "passport.json" in artifact_paths,
        "download_zip": bool(artifact_paths),
        "open_public_url": bool(getattr(result, "package_url", None)),
        "push_to_s3": False,
        "generate_qr": "qr.png" not in artifact_paths and bool(getattr(result, "package_url", None)),
    }


def build_user_inputs(
    *,
    product_group: str,
    brand_name: str,
    product_name: str = "",
    description: str = "",
    product_identifier: str = "",
    operator_identifier: str = "",
    facility_identifier: str = "",
    resolver_url: str = "",
    battery_category: str = "",
    battery_chemistry: str = "",
    declaration_reference: str = "",
    technical_documentation_reference: str = "",
    carbon_footprint_reference: str = "",
    recycled_content_reference: str = "",
    supplier_evidence_note: str = "",
) -> dict[str, Any]:
    user_inputs: dict[str, Any] = {}

    mapping = {
        "product_group": product_group,
        "brand_name": brand_name,
        "product_name": product_name,
        "product_description": description,
        "persistent_identifier_value": product_identifier,
        "operator_identifier_value": operator_identifier,
        "facility_identifier_value": facility_identifier,
        "public_resolver_url": resolver_url,
        "battery_category": battery_category,
        "battery_chemistry": battery_chemistry,
        "declaration_reference": declaration_reference,
        "technical_documentation_reference": technical_documentation_reference,
        "carbon_footprint_reference": carbon_footprint_reference,
        "recycled_content_reference": recycled_content_reference,
        "supplier_evidence_note": supplier_evidence_note,
    }

    for key, value in mapping.items():
        if isinstance(value, str) and value.strip():
            user_inputs[key] = value.strip()

    return user_inputs


def _apply_s3_env(config: S3UIConfig) -> None:
    values = {
        "AWS_REGION": config.region,
        "AWS_S3_BUCKET": config.bucket,
        "AWS_S3_PREFIX": config.prefix,
        "PUBLIC_BASE_URL": config.public_base_url,
        "AWS_ENDPOINT_URL": config.endpoint_url,
        "AWS_ACCESS_KEY_ID": config.access_key_id,
        "AWS_SECRET_ACCESS_KEY": config.secret_access_key,
        "AWS_SESSION_TOKEN": config.session_token,
    }

    for key, value in values.items():
        if value:
            os.environ[key] = value


def build_storage(
    *,
    storage_mode: str,
    output_dir: str | Path,
    s3_config: S3UIConfig | None = None,
):
    mode = validate_storage_mode(storage_mode)

    if mode == "local":
        return LocalStorage(output_dir=output_dir), mode

    if s3_config is not None:
        _apply_s3_env(s3_config)

    return S3Storage(), mode


def build_passport_pipeline(
    *,
    runtime_mode: str,
    storage_mode: str,
    output_dir: str | Path,
    timeout: int,
    s3_config: S3UIConfig | None = None,
) -> tuple[PassportPipeline, str]:
    mode = validate_runtime_mode(runtime_mode)
    storage, resolved_storage_mode = build_storage(
        storage_mode=storage_mode,
        output_dir=output_dir,
        s3_config=s3_config,
    )

    if mode == "demo_mock":
        vision_agent = DemoVisionAgent()
    else:
        vision_agent = VisionAgent(
            client=GemmaClient(
                timeout=timeout,
                validate_on_init=False,
            )
        )

    pipeline = PassportPipeline(
        agents={
            "vision": vision_agent,
            "regulatory": RegulatoryConsultant(client=None),
            "legal": LegalAgent(client=None),
            "lca": LCASpecialist(client=None),
            "gs1": GS1Specialist(client=None),
            "audit": DataAuditAgent(client=None),
            "dpp_generator": DPPGenerator(client=None),
            "passport_renderer": PassportRenderer(),
            "gap_report": GapReportGenerator(client=None),
            "qr_generator": QRCodeGenerator(),
        },
        storage=storage,
        staging_output_dir=output_dir,
    )

    return pipeline, resolved_storage_mode


def create_zip_package(
    passport_id: str,
    artifact_paths: dict[str, Path] | None = None,
    output_dir: str | Path = "output",
) -> str:
    if artifact_paths:
        paths = {name: Path(path) for name, path in artifact_paths.items()}
        package_dir = next(iter(paths.values())).parent
    else:
        package_dir = Path(output_dir) / passport_id
        if not package_dir.exists():
            raise FileNotFoundError(f"Passport package directory not found: {package_dir}")
        paths = {
            path.name: path
            for path in package_dir.iterdir()
            if path.is_file() and path.name != "passport_package.zip"
        }

    if not paths:
        raise FileNotFoundError(f"No artifact files found for passport package {passport_id}")

    zip_path = package_dir / "passport_package.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, source_path in sorted(paths.items()):
            if source_path.exists() and source_path.is_file() and source_path.name != zip_path.name:
                archive.write(source_path, arcname=filename)

    return str(zip_path)


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"<p>Could not read artifact: {html.escape(str(exc))}</p>"


def _artifact_html_preview(path: Path | None, *, title: str) -> str:
    if path is None:
        return f"<section class='pa-preview-empty'><h3>{html.escape(title)}</h3><p>No artifact generated yet.</p></section>"

    path = Path(path)
    if not path.exists():
        return (
            f"<section class='pa-preview-empty'><h3>{html.escape(title)}</h3>"
            f"<p>Artifact path does not exist: <code>{html.escape(str(path))}</code></p></section>"
        )

    if path.suffix.lower() == ".html":
        return _safe_read_text(path)

    return (
        f"<section class='pa-preview-empty'><h3>{html.escape(title)}</h3>"
        f"<p>Artifact generated at <code>{html.escape(str(path))}</code>.</p></section>"
    )


def _artifact_file_uri(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return Path(path).resolve().as_uri()
    except ValueError:
        return None


def _build_artifact_links(result: Any) -> dict[str, str]:
    artifact_paths = getattr(result, "artifact_paths", {}) or {}
    links: dict[str, str] = {}

    for name, path in artifact_paths.items():
        uri = _artifact_file_uri(Path(path))
        if uri:
            links[name] = uri

    if getattr(result, "package_url", None):
        links["public_passport_url"] = str(result.package_url)

    if getattr(result, "qr_url", None):
        links["public_qr_url"] = str(result.qr_url)

    return links


def _build_actions_html(result: Any | None) -> str:
    action_state = build_action_state(result)
    if result is None or not getattr(result, "success", False):
        return """
        <div class=\"pa-actions disabled\">
          <h3>Workspace Tools</h3>
          <button disabled>Open Passport</button>
          <button disabled>Open Gap Report</button>
          <button disabled>Download JSON</button>
          <button disabled>Download ZIP</button>
          <button disabled>Open Public URL</button>
          <p>Generate a passport first.</p>
        </div>
        """

    links = _build_artifact_links(result)
    rows = []

    def add_link(label: str, key: str, enabled: bool) -> None:
        if enabled and key in links:
            rows.append(f"<a class='pa-tool' href='{html.escape(links[key])}' target='_blank'>{html.escape(label)}</a>")
        else:
            rows.append(f"<button class='pa-tool' disabled>{html.escape(label)}</button>")

    add_link("Open Passport", "passport.html", action_state["open_passport"])
    add_link("Open Gap Report", "gap_report.html", action_state["open_gap_report"])
    add_link("Open Public URL", "public_passport_url", action_state["open_public_url"])
    add_link("Open QR", "qr.png", "qr.png" in links)

    return "<div class='pa-actions'><h3>Workspace Tools</h3>" + "".join(rows) + "</div>"


def _format_progress_html(events: list[dict[str, str]]) -> str:
    items = []
    for event in events:
        state = html.escape(event.get("state", "pending"))
        label = html.escape(event.get("label", "Unnamed step"))
        items.append(f"<li class='pa-step pa-step-{state}'><span>{state}</span>{label}</li>")
    return "<ol class='pa-progress'>" + "".join(items) + "</ol>"


def _completed_progress_events() -> list[dict[str, str]]:
    return [{"label": label, "state": "completed"} for label in PROGRESS_EVENTS]


def _failed_progress_events(message: str) -> list[dict[str, str]]:
    events = [{"label": label, "state": "pending"} for label in PROGRESS_EVENTS]
    if events:
        events[0] = {"label": f"Generation failed: {message}", "state": "failed"}
    return events


def _format_run_summary(result: Any | None, *, runtime_mode: str, storage_mode: str, zip_path: str | None) -> str:
    if result is None:
        return "No run has completed yet."

    lines = [
        f"### Run Summary",
        f"- Runtime mode: `{runtime_mode}`",
        f"- Storage mode: `{storage_mode}`",
        f"- Passport ID: `{getattr(result, 'passport_id', 'n/a')}`",
        f"- Success: `{getattr(result, 'success', False)}`",
        f"- Readiness score: `{getattr(result, 'readiness_score', None)}`",
        f"- Readiness verdict: `{getattr(result, 'readiness_verdict', None)}`",
        f"- Publishable: `{getattr(result, 'is_publishable', None)}`",
        f"- Package URL: `{getattr(result, 'package_url', None)}`",
        f"- QR URL: `{getattr(result, 'qr_url', None)}`",
    ]

    if zip_path:
        lines.append(f"- ZIP: `{zip_path}`")

    warnings = getattr(result, "warnings", []) or []
    errors = getattr(result, "errors", []) or []

    if warnings:
        lines.append("\n#### Warnings")
        lines.extend(f"- {warning}" for warning in warnings)

    if errors:
        lines.append("\n#### Errors")
        lines.extend(f"- {error}" for error in errors)

    return "\n".join(lines)


def run_generation(
    *,
    image_path: str | Path | None,
    description: str,
    product_group: str,
    brand_name: str,
    product_name: str = "",
    runtime_mode: str = "demo_mock",
    storage_mode: str = "local",
    output_dir: str | Path = "output",
    timeout: int = 600,
    product_identifier: str = "",
    operator_identifier: str = "",
    facility_identifier: str = "",
    resolver_url: str = "",
    battery_category: str = "",
    battery_chemistry: str = "",
    declaration_reference: str = "",
    technical_documentation_reference: str = "",
    carbon_footprint_reference: str = "",
    recycled_content_reference: str = "",
    supplier_evidence_note: str = "",
    s3_config: S3UIConfig | None = None,
    pipeline_factory: Callable[..., tuple[Any, str]] | None = None,
) -> UIRunView:
    runtime_mode = validate_runtime_mode(runtime_mode)
    storage_mode = validate_storage_mode(storage_mode)

    validation_errors = validate_minimum_inputs(
        image_path=image_path,
        product_group=product_group,
        brand_name=brand_name,
        description=description,
    )
    if validation_errors:
        progress_events = _failed_progress_events(validation_errors[0])
        state = build_initial_ui_state()
        state.update(
            {
                "has_started": True,
                "is_running": False,
                "runtime_mode": runtime_mode,
                "storage_mode": storage_mode,
                "errors": validation_errors,
                "progress_events": progress_events,
            }
        )
        return UIRunView(
            success=False,
            messages=[("PassportAI", "Generation was not started because required inputs are missing.")],
            progress_html=_format_progress_html(progress_events),
            passport_preview_html=EMPTY_STATE_GUIDANCE,
            gap_report_preview_html="",
            passport_json=None,
            qr_path=None,
            run_summary_markdown="\n".join(f"- {error}" for error in validation_errors),
            actions_html=_build_actions_html(None),
            zip_path=None,
            state=state,
        )

    user_inputs = build_user_inputs(
        product_group=product_group,
        brand_name=brand_name,
        product_name=product_name,
        description=description,
        product_identifier=product_identifier,
        operator_identifier=operator_identifier,
        facility_identifier=facility_identifier,
        resolver_url=resolver_url,
        battery_category=battery_category,
        battery_chemistry=battery_chemistry,
        declaration_reference=declaration_reference,
        technical_documentation_reference=technical_documentation_reference,
        carbon_footprint_reference=carbon_footprint_reference,
        recycled_content_reference=recycled_content_reference,
        supplier_evidence_note=supplier_evidence_note,
    )

    try:
        if pipeline_factory is None:
            pipeline, resolved_storage_mode = build_passport_pipeline(
                runtime_mode=runtime_mode,
                storage_mode=storage_mode,
                output_dir=output_dir,
                timeout=timeout,
                s3_config=s3_config,
            )
        else:
            pipeline, resolved_storage_mode = pipeline_factory(
                runtime_mode=runtime_mode,
                storage_mode=storage_mode,
                output_dir=output_dir,
                timeout=timeout,
                s3_config=s3_config,
            )

        result = pipeline.run(
            image_path=Path(image_path),
            description=description,
            user_inputs=user_inputs,
        )
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        progress_events = _failed_progress_events(error_message)
        state = build_initial_ui_state()
        state.update(
            {
                "has_started": True,
                "is_running": False,
                "runtime_mode": runtime_mode,
                "storage_mode": storage_mode,
                "latest_input": user_inputs,
                "errors": [error_message],
                "progress_events": progress_events,
            }
        )
        return UIRunView(
            success=False,
            messages=[("PassportAI", error_message)],
            progress_html=_format_progress_html(progress_events),
            passport_preview_html=EMPTY_STATE_GUIDANCE,
            gap_report_preview_html="",
            passport_json=None,
            qr_path=None,
            run_summary_markdown=f"Generation failed: `{error_message}`",
            actions_html=_build_actions_html(None),
            zip_path=None,
            state=state,
        )

    vision_output = (getattr(result, "agent_outputs", {}) or {}).get("vision")
    live_vision_failed = (
        runtime_mode == "live_gemma"
        and isinstance(vision_output, dict)
        and vision_output.get("success") is not True
    )

    artifact_paths = getattr(result, "artifact_paths", {}) or {}
    zip_path: str | None = None
    if getattr(result, "success", False) and artifact_paths:
        try:
            zip_path = create_zip_package(
                getattr(result, "passport_id"),
                artifact_paths={name: Path(path) for name, path in artifact_paths.items()},
                output_dir=output_dir,
            )
        except Exception:
            zip_path = None

    progress_events = _completed_progress_events() if getattr(result, "success", False) else _failed_progress_events("Pipeline returned success=false")
    errors = list(getattr(result, "errors", []) or [])
    warnings = list(getattr(result, "warnings", []) or [])

    if runtime_mode == "demo_mock":
        warnings.append("Demo mode: fixture vision output is used.")

    if live_vision_failed:
        errors.append(
            "Gemma vision analysis failed. Retry live mode after freeing memory or switch to demo mode."
        )

    passport_path = Path(artifact_paths["passport.html"]) if "passport.html" in artifact_paths else None
    gap_path = Path(artifact_paths["gap_report.html"]) if "gap_report.html" in artifact_paths else None
    qr_path = str(artifact_paths["qr.png"]) if "qr.png" in artifact_paths else None

    state = build_initial_ui_state()
    state.update(
        {
            "has_started": True,
            "is_running": False,
            "runtime_mode": runtime_mode,
            "storage_mode": resolved_storage_mode,
            "latest_input": user_inputs,
            "latest_result": {
                "success": bool(getattr(result, "success", False)) and not live_vision_failed,
                "passport_id": getattr(result, "passport_id", None),
                "package_url": getattr(result, "package_url", None),
                "qr_url": getattr(result, "qr_url", None),
                "readiness_score": getattr(result, "readiness_score", None),
                "readiness_verdict": getattr(result, "readiness_verdict", None),
                "is_publishable": getattr(result, "is_publishable", None),
            },
            "artifact_paths": {name: str(path) for name, path in artifact_paths.items()},
            "artifact_urls": _build_artifact_links(result),
            "progress_events": progress_events,
            "errors": errors,
            "warnings": warnings,
        }
    )

    message_content = (
        "Generated passport package successfully."
        if getattr(result, "success", False) and not live_vision_failed
        else "Generation finished with errors."
    )
    if runtime_mode == "demo_mock":
        message_content += " Demo mode used fixture vision output."

    return UIRunView(
        success=bool(getattr(result, "success", False)) and not live_vision_failed,
        messages=[("PassportAI", message_content)],
        progress_html=_format_progress_html(progress_events),
        passport_preview_html=_artifact_html_preview(passport_path, title="Passport"),
        gap_report_preview_html=_artifact_html_preview(gap_path, title="Gap Report"),
        passport_json=getattr(result, "passport_json", None),
        qr_path=qr_path,
        run_summary_markdown=_format_run_summary(
            result,
            runtime_mode=runtime_mode,
            storage_mode=resolved_storage_mode,
            zip_path=zip_path,
        ),
        actions_html=_build_actions_html(result),
        zip_path=zip_path,
        state=state,
    )


def _make_s3_config(
    region: str,
    bucket: str,
    prefix: str,
    public_base_url: str,
    endpoint_url: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str,
) -> S3UIConfig:
    return S3UIConfig(
        region=region.strip(),
        bucket=bucket.strip(),
        prefix=prefix.strip() or "passports",
        public_base_url=public_base_url.strip(),
        endpoint_url=endpoint_url.strip(),
        access_key_id=access_key_id.strip(),
        secret_access_key=secret_access_key.strip(),
        session_token=session_token.strip(),
    )


def _gradio_generate(
    image_path: str | None,
    product_group: str,
    product_name: str,
    brand_name: str,
    description: str,
    runtime_mode: str,
    storage_mode: str,
    product_identifier: str,
    operator_identifier: str,
    facility_identifier: str,
    resolver_url: str,
    battery_category: str,
    battery_chemistry: str,
    declaration_reference: str,
    technical_documentation_reference: str,
    carbon_footprint_reference: str,
    recycled_content_reference: str,
    supplier_evidence_note: str,
    output_dir: str,
    timeout: int,
    s3_region: str,
    s3_bucket: str,
    s3_prefix: str,
    s3_public_base_url: str,
    s3_endpoint_url: str,
    s3_access_key_id: str,
    s3_secret_access_key: str,
    s3_session_token: str,
    current_state: dict[str, Any] | None,
):
    del current_state

    running_state = build_initial_ui_state()
    running_state.update(
        {
            "has_started": True,
            "is_running": True,
            "runtime_mode": runtime_mode,
            "storage_mode": storage_mode,
            "progress_events": [
                {"label": PROGRESS_EVENTS[0], "state": "running"},
                *[{"label": label, "state": "pending"} for label in PROGRESS_EVENTS[1:]],
            ],
        }
    )

    yield (
        [("PassportAI", "Passport generation started.")],
        _format_progress_html(running_state["progress_events"]),
        EMPTY_STATE_GUIDANCE,
        "",
        None,
        None,
        "Generation running...",
        _build_actions_html(None),
        None,
        running_state,
    )

    view = run_generation(
        image_path=image_path,
        description=description,
        product_group=product_group,
        brand_name=brand_name,
        product_name=product_name,
        runtime_mode=runtime_mode,
        storage_mode=storage_mode,
        output_dir=output_dir or "output",
        timeout=int(timeout or 600),
        product_identifier=product_identifier,
        operator_identifier=operator_identifier,
        facility_identifier=facility_identifier,
        resolver_url=resolver_url,
        battery_category=battery_category,
        battery_chemistry=battery_chemistry,
        declaration_reference=declaration_reference,
        technical_documentation_reference=technical_documentation_reference,
        carbon_footprint_reference=carbon_footprint_reference,
        recycled_content_reference=recycled_content_reference,
        supplier_evidence_note=supplier_evidence_note,
        s3_config=_make_s3_config(
            region=s3_region,
            bucket=s3_bucket,
            prefix=s3_prefix,
            public_base_url=s3_public_base_url,
            endpoint_url=s3_endpoint_url,
            access_key_id=s3_access_key_id,
            secret_access_key=s3_secret_access_key,
            session_token=s3_session_token,
        ),
    )

    yield (
        view.messages,
        view.progress_html,
        view.passport_preview_html,
        view.gap_report_preview_html,
        view.passport_json,
        view.qr_path,
        view.run_summary_markdown,
        view.actions_html,
        view.zip_path,
        view.state,
    )


def _ui_css() -> str:
    return """
    .pa-empty { padding: 28px; border: 1px solid #e5e7eb; border-radius: 24px; background: #fff; }
    .pa-empty h2 { font-family: Georgia, 'Times New Roman', serif; font-size: 32px; margin: 0 0 8px; }
    .pa-empty-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
    .pa-empty section { border: 1px solid #e5e7eb; border-radius: 18px; padding: 14px; background: #fafafa; }
    .pa-progress { display: grid; gap: 8px; padding: 0; margin: 0; list-style: none; }
    .pa-step { border: 1px solid #e5e7eb; border-radius: 14px; padding: 10px 12px; background: #fff; }
    .pa-step span { display: inline-block; min-width: 76px; font-size: 11px; font-weight: 800; text-transform: uppercase; color: #667085; }
    .pa-step-completed { border-color: #bbf7d0; background: #f0fdf4; }
    .pa-step-running { border-color: #bfdbfe; background: #eff6ff; }
    .pa-step-failed { border-color: #fecaca; background: #fef2f2; }
    .pa-actions { display: grid; gap: 10px; padding: 14px; border: 1px solid #e5e7eb; border-radius: 18px; background: #fff; }
    .pa-actions h3 { margin: 0 0 4px; font-size: 13px; text-transform: uppercase; letter-spacing: .12em; color: #667085; }
    .pa-tool { display: block; width: 100%; border: 1px solid #d1d5db; border-radius: 12px; padding: 10px 12px; background: #fff; color: #111827; text-decoration: none; font-weight: 700; text-align: left; }
    .pa-tool:disabled, .pa-actions.disabled button { opacity: .48; cursor: not-allowed; }
    .pa-preview-empty { padding: 24px; border: 1px dashed #d1d5db; border-radius: 18px; background: #fafafa; }
    @media (max-width: 960px) { .pa-empty-grid { grid-template-columns: 1fr; } }
    """


def build_interface():
    if gr is None:
        raise ImportError(
            "gradio is required for PassportAI UI. Install dependencies with: pip install -r requirements.txt"
        )

    with gr.Blocks(
        title="PassportAI",
        css=_ui_css(),
    ) as interface:
        state = gr.State(build_initial_ui_state())

        gr.Markdown(
            """
            # PassportAI
            Digital Product Passport workspace for photo-to-passport generation, evidence review, cloud publishing, and QR packaging.
            """
        )

        with gr.Row():
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    label="Workspace Chat",
                    value=[],
                    height=260,
                )

                image_input = gr.Image(
                    label="Product Photo",
                    type="filepath",
                    sources=["upload", "clipboard"],
                )

                product_group = gr.Dropdown(
                    choices=SUPPORTED_PRODUCT_GROUPS,
                    value="batteries",
                    label="Product Group",
                )
                product_name = gr.Textbox(label="Product Name", placeholder="AA alkaline battery pack")
                brand_name = gr.Textbox(label="Brand Name", placeholder="Demo Brand")
                description = gr.Textbox(
                    label="Product Description",
                    lines=3,
                    placeholder="Describe the product and any visible evidence.",
                )

                with gr.Row():
                    runtime_mode = gr.Radio(
                        choices=RUNTIME_MODES,
                        value="demo_mock",
                        label="Runtime Mode",
                    )
                    storage_mode = gr.Radio(
                        choices=STORAGE_MODES,
                        value="local",
                        label="Storage Mode",
                    )

                with gr.Accordion("Optional Evidence", open=False):
                    product_identifier = gr.Textbox(label="Product Identifier / GTIN")
                    operator_identifier = gr.Textbox(label="Operator Identifier")
                    facility_identifier = gr.Textbox(label="Facility Identifier")
                    resolver_url = gr.Textbox(label="Resolver URL Override")
                    battery_category = gr.Textbox(label="Battery Category")
                    battery_chemistry = gr.Textbox(label="Battery Chemistry")
                    declaration_reference = gr.Textbox(label="Declaration Reference")
                    technical_documentation_reference = gr.Textbox(label="Technical Documentation Reference")
                    carbon_footprint_reference = gr.Textbox(label="Carbon Footprint Reference")
                    recycled_content_reference = gr.Textbox(label="Recycled Content Reference")
                    supplier_evidence_note = gr.Textbox(label="Supplier Evidence Note", lines=2)

                with gr.Accordion("Runtime / Storage Settings", open=False):
                    output_dir = gr.Textbox(label="Local Output Directory", value="output")
                    timeout = gr.Number(label="Ollama Timeout Seconds", value=600, precision=0)
                    gr.Markdown("S3 fields are optional when `.env` is already configured.")
                    s3_region = gr.Textbox(label="AWS Region", value=os.getenv("AWS_REGION", "eu-west-1"))
                    s3_bucket = gr.Textbox(label="S3 Bucket", value=os.getenv("AWS_S3_BUCKET", ""))
                    s3_prefix = gr.Textbox(label="S3 Prefix", value=os.getenv("AWS_S3_PREFIX", "passports"))
                    s3_public_base_url = gr.Textbox(label="Public Base URL", value=os.getenv("PUBLIC_BASE_URL", ""))
                    s3_endpoint_url = gr.Textbox(label="S3 Endpoint URL", value=os.getenv("AWS_ENDPOINT_URL", ""))
                    s3_access_key_id = gr.Textbox(label="AWS Access Key ID", value="", type="password")
                    s3_secret_access_key = gr.Textbox(label="AWS Secret Access Key", value="", type="password")
                    s3_session_token = gr.Textbox(label="AWS Session Token", value="", type="password")

                generate_button = gr.Button("Generate Passport", variant="primary")

            with gr.Column(scale=7):
                progress_html = gr.HTML(label="Progress", value=EMPTY_STATE_GUIDANCE)
                actions_html = gr.HTML(value=_build_actions_html(None))

                with gr.Tabs():
                    with gr.Tab("Passport"):
                        passport_preview_html = gr.HTML(value=EMPTY_STATE_GUIDANCE)
                    with gr.Tab("Gap Report"):
                        gap_report_preview_html = gr.HTML(value="")
                    with gr.Tab("JSON"):
                        passport_json = gr.JSON(label="passport.json")
                    with gr.Tab("QR"):
                        qr_image = gr.Image(label="qr.png", type="filepath")
                    with gr.Tab("Run Summary"):
                        run_summary = gr.Markdown(value="No run has completed yet.")
                        zip_file = gr.File(label="Download ZIP")

        generate_button.click(
            fn=_gradio_generate,
            inputs=[
                image_input,
                product_group,
                product_name,
                brand_name,
                description,
                runtime_mode,
                storage_mode,
                product_identifier,
                operator_identifier,
                facility_identifier,
                resolver_url,
                battery_category,
                battery_chemistry,
                declaration_reference,
                technical_documentation_reference,
                carbon_footprint_reference,
                recycled_content_reference,
                supplier_evidence_note,
                output_dir,
                timeout,
                s3_region,
                s3_bucket,
                s3_prefix,
                s3_public_base_url,
                s3_endpoint_url,
                s3_access_key_id,
                s3_secret_access_key,
                s3_session_token,
                state,
            ],
            outputs=[
                chatbot,
                progress_html,
                passport_preview_html,
                gap_report_preview_html,
                passport_json,
                qr_image,
                run_summary,
                actions_html,
                zip_file,
                state,
            ],
        )

    return interface


if __name__ == "__main__":
    port = int(os.getenv("GRADIO_PORT", "7860"))
    app = build_interface()
    app.launch(server_name="127.0.0.1", server_port=port, share=False)
