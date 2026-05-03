from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

from src.ui.gradio_app import build_interface


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the PassportAI Gradio UI.")
    parser.add_argument(
        "--host",
        default=os.getenv("GRADIO_HOST", "127.0.0.1"),
        help="Host to bind. Use 127.0.0.1 for local-only development.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GRADIO_PORT", "7860")),
        help="Port for the Gradio UI.",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Enable Gradio share link. Off by default.",
    )
    args = parser.parse_args()

    interface = build_interface()
    interface.launch(server_name=args.host, server_port=args.port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
