from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

from agents.data_audit_agent import DataAuditAgent
from agents.gs1_specialist import GS1Specialist
from agents.lca_specialist import LCASpecialist
from agents.legal_agent import LegalAgent
from agents.regulatory_consultant import RegulatoryConsultant
from agents.vision_agent import VisionAgent
from src.core.dpp_generator import DPPGenerator
from src.core.gap_report import GapReportGenerator
from src.core.passport_renderer import PassportRenderer
from src.core.gemma_client import GemmaClient, GemmaClientError
from src.core.pipeline import PassportPipeline
from src.storage.local import LocalStorage


def _build_user_inputs(args: argparse.Namespace) -> dict[str, Any]:
    user_inputs: dict[str, Any] = {}

    for key in (
        "product_group",
        "brand_name",
        "model_name",
        "model_number",
        "serial_number",
        "batch_lot",
        "persistent_identifier_value",
        "operator_identifier_value",
        "facility_identifier_value",
        "public_resolver_url",
    ):
        value = getattr(args, key, None)
        if value:
            user_inputs[key] = value

    if args.product_name:
        user_inputs["product_name"] = args.product_name

    if args.product_description:
        user_inputs["product_description"] = args.product_description

    return user_inputs


def _require_live_vision(result: Any) -> None:
    vision = result.agent_outputs.get("vision") if result.agent_outputs else None

    if not isinstance(vision, dict):
        raise RuntimeError("VisionAgent did not produce an output envelope.")

    if vision.get("success") is not True:
        raise RuntimeError(f"VisionAgent failed: {vision.get('error')}")

    if vision.get("is_mock") is True:
        raise RuntimeError(
            "VisionAgent ran in mock mode. Demo command requires Gemma-backed vision."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PassportAI demo pipeline with Gemma-backed vision."
    )

    parser.add_argument("--image", required=True, type=Path, help="Path to product photo")
    parser.add_argument("--description", default="", help="Optional product description")
    parser.add_argument(
        "--product-group",
        choices=["textiles", "batteries", "electrical_appliances"],
    )
    parser.add_argument("--product-name")
    parser.add_argument("--product-description")
    parser.add_argument("--brand-name")
    parser.add_argument("--model-name")
    parser.add_argument("--model-number")
    parser.add_argument("--serial-number")
    parser.add_argument("--batch-lot")
    parser.add_argument("--persistent-identifier-value")
    parser.add_argument("--operator-identifier-value")
    parser.add_argument("--facility-identifier-value")
    parser.add_argument("--public-resolver-url")
    parser.add_argument("--output-dir", default="output", type=Path)
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Ollama request timeout in seconds. Local cold-start for large Gemma models can be slow.",
    )
    parser.add_argument(
        "--skip-ollama-check",
        action="store_true",
        help="Skip preflight model availability check; pipeline still fails if Ollama is unreachable.",
    )

    args = parser.parse_args()

    if not args.image.exists():
        print(f"ERROR: image not found: {args.image}", file=sys.stderr)
        return 2

    try:
        client = GemmaClient(
            timeout=args.timeout,
            validate_on_init=not args.skip_ollama_check,
        )
    except (ImportError, ValueError, GemmaClientError) as exc:
        print(f"ERROR: Gemma/Ollama preflight failed: {exc}", file=sys.stderr)
        print(
            "Start Ollama and pull the model, e.g.: ollama serve && ollama pull gemma4:e4b",
            file=sys.stderr,
        )
        return 2

    storage = LocalStorage(output_dir=args.output_dir)

    pipeline = PassportPipeline(
        agents={
            "vision": VisionAgent(client=client),

            # Current contest slice keeps these deterministic. Do not replace them
            # with unconstrained LLM synthesis before their contracts are locked.
            "regulatory": RegulatoryConsultant(client=None),
            "legal": LegalAgent(client=None),
            "lca": LCASpecialist(client=None),
            "gs1": GS1Specialist(client=None),

            "audit": DataAuditAgent(client=None),
            "dpp_generator": DPPGenerator(client=None),
            "passport_renderer": PassportRenderer(),
            "gap_report": GapReportGenerator(client=None),
        },
        storage=storage,
    )

    result = pipeline.run(
        image_path=args.image,
        description=args.description,
        user_inputs=_build_user_inputs(args),
    )

    try:
        _require_live_vision(result)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = {
        "success": result.success,
        "passport_id": result.passport_id,
        "readiness_score": result.readiness_score,
        "readiness_verdict": result.readiness_verdict,
        "is_publishable": result.is_publishable,
        "package_url": result.package_url,
        "artifacts": {
            name: str(path)
            for name, path in result.artifact_paths.items()
        },
        "errors": result.errors,
        "warnings": result.warnings,
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if not result.success:
        return 1

    print("\nGenerated artifacts:")
    for name, path in result.artifact_paths.items():
        print(f"- {name}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main()) 
