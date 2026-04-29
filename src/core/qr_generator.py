from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class QRCodeGenerator:
    """Generate QR/data-carrier artifacts for PassportAI packages.

    The QR code is a derived artifact. It encodes the public human-readable
    passport URL and must not decide readiness, mutate product facts, or act as
    a source of truth for the DPP.
    """

    DEFAULT_FILENAME = "qr.png"

    def generate(
        self,
        *,
        target_url: str,
        output_dir: str | Path,
        passport_id: str,
        filename: str = DEFAULT_FILENAME,
        print_ready: bool = True,
    ) -> Path:
        """Generate a QR PNG for a public passport URL.

        Args:
            target_url: Public URL to encode. Must be http(s).
            output_dir: Local package directory where qr.png is written.
            passport_id: Current passport ID, used only for error context.
            filename: Output filename. Defaults to qr.png.
            print_ready: If true, use a larger module size suitable for print.

        Returns:
            Path to the generated QR PNG.

        Raises:
            ValueError: If the target URL or filename is invalid.
            RuntimeError: If qrcode/Pillow generation fails.
        """
        normalized_url = self._validate_target_url(target_url)
        output_name = self._validate_filename(filename)

        package_dir = Path(output_dir)
        package_dir.mkdir(parents=True, exist_ok=True)
        output_path = package_dir / output_name

        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_M
        except ImportError as exc:
            raise RuntimeError(
                "qrcode[pil] is required to generate QR artifacts. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc

        box_size = 15 if print_ready else 10
        border = 4 if print_ready else 3

        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=ERROR_CORRECT_M,
                box_size=box_size,
                border=border,
            )
            qr.add_data(normalized_url)
            qr.make(fit=True)
            image: Any = qr.make_image(fill_color="black", back_color="white")

            # PIL-backed images may be palette/1-bit. Convert when available so
            # the artifact is broadly browser/print compatible.
            if hasattr(image, "convert"):
                image = image.convert("RGB")

            image.save(output_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to generate QR artifact for passport {passport_id}: {exc}"
            ) from exc

        return output_path

    def _validate_target_url(self, value: str) -> str:
        target = (value or "").strip()
        if not target:
            raise ValueError("QR target_url must not be empty")

        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "QR target_url must be an absolute http(s) URL pointing to passport.html"
            )

        return target

    def _validate_filename(self, value: str) -> str:
        filename = (value or "").replace("\\", "/").strip("/")
        if not filename:
            raise ValueError("QR filename must not be empty")

        if "/" in filename:
            raise ValueError("QR filename must be a single package filename")

        if not filename.lower().endswith(".png"):
            raise ValueError("QR filename must end with .png")

        return filename
