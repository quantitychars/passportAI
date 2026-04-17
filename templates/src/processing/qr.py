"""
src/processing/qr.py — QR Code Generator

IMPORTANT: QR code generation is the LAST step in the pipeline.
The QR encodes the passport_url, which is only known after storage
(either local server URL or S3 URL).

Never call generate_qr() before storage.save_package() returns the URL.

Output: PNG QR code image suitable for printing (300 DPI equivalent).

Dependencies:
    pip install qrcode[pil]

Usage:
    from src.processing.qr import generate_qr
    from pathlib import Path

    # ALWAYS after storage.save_package() returns passport_url
    qr_path = generate_qr(
        passport_url="http://localhost:8000/3f8a1b2c-...",
        output_path=Path("output/3f8a1b2c-.../qr.png"),
    )
"""

from pathlib import Path


QR_BOX_SIZE = 10        # Pixels per QR module
QR_BORDER = 4           # Modules for quiet zone (minimum 4 per QR spec)
QR_ERROR_CORRECTION = "L"  # L=7%, M=15%, Q=25%, H=30% error correction


def generate_qr(
    passport_url: str,
    output_path: Path | None = None,
    box_size: int = QR_BOX_SIZE,
    border: int = QR_BORDER,
    error_correction: str = QR_ERROR_CORRECTION,
) -> Path:
    """Generate a QR code PNG for a passport URL.

    This function MUST be called LAST in the pipeline, after the passport_url
    has been confirmed by the storage handler.

    Args:
        passport_url: The public URL to encode in the QR code.
                      Example: "http://localhost:8000/3f8a1b2c-e4d5-..."
        output_path: Path to save the QR PNG. Defaults to ./qr.png.
        box_size: Pixels per QR module. Default 10 = ~300px for typical QR.
        border: Quiet zone in modules. Minimum 4 per QR spec.
        error_correction: Error correction level ("L", "M", "Q", "H").

    Returns:
        Path to the saved QR code PNG file.

    Raises:
        ImportError: If qrcode[pil] is not installed.
        ValueError: If passport_url is empty or None.

    Example:
        >>> from src.processing.qr import generate_qr
        >>> from pathlib import Path
        >>> # Called AFTER storage returns the URL
        >>> qr = generate_qr(
        ...     passport_url="http://localhost:8000/abc123",
        ...     output_path=Path("output/abc123/qr.png")
        ... )
        >>> print(qr.stat().st_size)  # Should be > 1000 bytes

    Note:
        QR codes with longer URLs (e.g. S3 URLs) require higher error correction
        version numbers and produce larger codes. "L" (7%) is recommended
        for maximum data capacity.
    """
    if not passport_url:
        raise ValueError("passport_url cannot be empty")

    if output_path is None:
        output_path = Path("qr.png")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TODO: implement QR code generation
    # try:
    #     import qrcode
    #     from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
    # except ImportError:
    #     raise ImportError("qrcode not installed. Run: pip install qrcode[pil]")
    #
    # ec_map = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
    # ec = ec_map.get(error_correction.upper(), ERROR_CORRECT_L)
    #
    # qr = qrcode.QRCode(
    #     version=None,  # Auto-select minimum version
    #     error_correction=ec,
    #     box_size=box_size,
    #     border=border,
    # )
    # qr.add_data(passport_url)
    # qr.make(fit=True)
    #
    # img = qr.make_image(fill_color="black", back_color="white")
    # img.save(str(output_path))
    #
    # return output_path
    raise NotImplementedError("generate_qr() not yet implemented")


if __name__ == "__main__":
    test_url = "http://localhost:8000/3f8a1b2c-e4d5-4f6a-b789-0c1d2e3f4a5b"
    test_output = Path("/tmp/test_qr.png")
    print(f"Test URL: {test_url}")
    # TODO: uncomment after implementation
    # result = generate_qr(test_url, test_output)
    # print(f"QR saved to: {result}")
    # print(f"Size: {result.stat().st_size} bytes")
    print("generate_qr() not yet implemented")
