from __future__ import annotations

from pathlib import Path

import pytest

from src.core.qr_generator import QRCodeGenerator


def test_generate_writes_print_ready_qr_png(tmp_path):
    generator = QRCodeGenerator()

    qr_path = generator.generate(
        target_url="https://passportai.example.com/passports/demo/passport.html",
        output_dir=tmp_path,
        passport_id="demo",
    )

    assert qr_path == tmp_path / "qr.png"
    assert qr_path.exists()
    assert qr_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_generate_rejects_empty_target_url(tmp_path):
    generator = QRCodeGenerator()

    with pytest.raises(ValueError, match="target_url"):
        generator.generate(
            target_url="",
            output_dir=tmp_path,
            passport_id="demo",
        )


def test_generate_rejects_non_http_target_url(tmp_path):
    generator = QRCodeGenerator()

    with pytest.raises(ValueError, match="absolute http"):
        generator.generate(
            target_url="file:///tmp/passport.html",
            output_dir=tmp_path,
            passport_id="demo",
        )


def test_generate_rejects_nested_or_non_png_filename(tmp_path):
    generator = QRCodeGenerator()

    with pytest.raises(ValueError, match="single package filename"):
        generator.generate(
            target_url="https://passportai.example.com/passports/demo/passport.html",
            output_dir=tmp_path,
            passport_id="demo",
            filename="nested/qr.png",
        )

    with pytest.raises(ValueError, match="must end with .png"):
        generator.generate(
            target_url="https://passportai.example.com/passports/demo/passport.html",
            output_dir=tmp_path,
            passport_id="demo",
            filename="qr.jpg",
        )
