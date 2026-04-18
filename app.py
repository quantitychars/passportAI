"""
app.py — PassportAI Entry Point

Starts two servers concurrently:
  - FastAPI REST API on port FASTAPI_PORT (default: 8000)
  - Gradio Web UI on port GRADIO_PORT (default: 7860)

Usage:
    python app.py              # Start both servers
    python app.py --test       # Validate imports and exit

Environment:
    Configure via .env file (see .env.example)
"""

import argparse
import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Import validation — all core modules must be importable at startup
# ---------------------------------------------------------------------------

def check_imports() -> bool:
    """Validate that all required modules are importable.

    Returns:
        True if all imports succeed, False otherwise.
    """
    required = [
        "ollama",
        "fastapi",
        "gradio",
        "rembg",
        "PIL",
        "pyld",
        "qrcode",
        "jinja2",
        "dotenv",
        "uvicorn",
        "boto3",
    ]
    failed = []
    for module in required:
        try:
            __import__(module)
        except ImportError as e:
            failed.append(f"  MISSING: {module} — {e}")

    if failed:
        print("Import check FAILED:")
        for msg in failed:
            print(msg)
        print("\nRun: pip install -r requirements.txt")
        return False

    print("All imports OK")
    return True


def check_ollama() -> bool:
    """Verify Ollama server is running and the model is available.

    Returns:
        True if Ollama is reachable and model is present.
    """
    # TODO: implement Ollama health check
    # import ollama
    # try:
    #     models = ollama.list()
    #     model_names = [m["name"] for m in models.get("models", [])]
    #     model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    #     if model not in model_names:
    #         print(f"WARNING: Model '{model}' not found in Ollama. Run: ollama pull {model}")
    #         return False
    #     return True
    # except Exception as e:
    #     print(f"ERROR: Ollama not reachable at {os.getenv('OLLAMA_HOST')}: {e}")
    #     return False
    print("Ollama check: SKIPPED (--test mode)")
    return True


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def run_api_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the FastAPI server in a background thread.

    Args:
        host: Bind address.
        port: Port number.
    """
    # TODO: import and run uvicorn
    # import uvicorn
    # from src.server.passport_server import app as api_app
    # uvicorn.run(api_app, host=host, port=port, log_level="info")
    pass


def run_gradio_ui(port: int = 7860) -> None:
    """Launch the Gradio web interface.

    Args:
        port: Port number for Gradio.
    """
    # TODO: import and launch Gradio app
    # from src.ui.gradio_app import build_interface
    # interface = build_interface()
    # interface.launch(server_port=port, server_name="0.0.0.0")
    pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and start PassportAI."""
    parser = argparse.ArgumentParser(description="PassportAI — DPP Generator")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Validate imports and configuration, then exit.",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="Port for FastAPI server (default: 8000)",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=7860,
        help="Port for Gradio UI (default: 7860)",
    )
    args = parser.parse_args()

    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("WARNING: python-dotenv not installed. Using system environment variables.")

    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)

    if args.test:
        ok = check_imports()
        sys.exit(0 if ok else 1)

    # Check Ollama before starting
    if not check_ollama():
        print("ERROR: Ollama check failed. Start Ollama first: ollama serve")
        sys.exit(1)

    print(f"Starting PassportAI...")
    print(f"  API server: http://localhost:{args.api_port}")
    print(f"  Gradio UI:  http://localhost:{args.ui_port}")

    # Start FastAPI in background thread
    api_thread = threading.Thread(
        target=run_api_server,
        kwargs={"host": "0.0.0.0", "port": args.api_port},
        daemon=True,
        name="PassportAI-API",
    )
    api_thread.start()

    # Run Gradio in foreground (blocks)
    # TODO: replace with actual Gradio launch
    run_gradio_ui(port=args.ui_port)


if __name__ == "__main__":
    main()
