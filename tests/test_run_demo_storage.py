from __future__ import annotations

import argparse

import pytest

from scripts.run_demo_passport import _build_storage, _resolve_storage_mode
from src.storage.aws_s3 import S3Storage
from src.storage.local import LocalStorage


def test_resolve_storage_mode_prefers_cli_value(monkeypatch):
    monkeypatch.setenv("STORAGE_MODE", "s3")

    assert _resolve_storage_mode("local") == "local"


def test_resolve_storage_mode_uses_env_when_cli_missing(monkeypatch):
    monkeypatch.setenv("STORAGE_MODE", "s3")

    assert _resolve_storage_mode(None) == "s3"


def test_resolve_storage_mode_defaults_to_local(monkeypatch):
    monkeypatch.delenv("STORAGE_MODE", raising=False)

    assert _resolve_storage_mode(None) == "local"


def test_resolve_storage_mode_rejects_unknown(monkeypatch):
    monkeypatch.setenv("STORAGE_MODE", "ftp")

    with pytest.raises(ValueError, match="Unsupported storage mode"):
        _resolve_storage_mode(None)


def test_build_storage_returns_local_storage(tmp_path):
    args = argparse.Namespace(storage="local", output_dir=tmp_path / "out")

    storage, mode = _build_storage(args)

    assert mode == "local"
    assert isinstance(storage, LocalStorage)
    assert storage.output_dir == tmp_path / "out"


def test_build_storage_returns_s3_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_S3_BUCKET", "passportai-demo")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    class FakeS3Storage:
        def __init__(self):
            self.bucket = "passportai-demo"

    monkeypatch.setattr("scripts.run_demo_passport.S3Storage", FakeS3Storage)

    args = argparse.Namespace(storage="s3", output_dir=tmp_path / "out")

    storage, mode = _build_storage(args)

    assert mode == "s3"
    assert storage.bucket == "passportai-demo"
