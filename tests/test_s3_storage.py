from __future__ import annotations

from pathlib import Path

import pytest

from src.storage.aws_s3 import S3Storage
from src.storage.base import StorageError


class _NotFoundError(Exception):
    def __init__(self) -> None:
        self.response = {
            "Error": {"Code": "404"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }


class _FakePaginator:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.calls = []

    def paginate(self, **kwargs):
        self.calls.append(kwargs)
        yield from self.pages


class _FakeS3Client:
    def __init__(self) -> None:
        self.uploads = []
        self.heads = set()
        self.deleted = []
        self.paginator = _FakePaginator(
            [{"Contents": [{"Key": "passports/demo/passport.html"}, {"Key": "passports/demo/passport.json"}]}]
        )

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append(
            {
                "filename": filename,
                "bucket": bucket,
                "key": key,
                "ExtraArgs": ExtraArgs or {},
            }
        )
        self.heads.add((bucket, key))

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.heads:
            raise _NotFoundError()
        return {"ContentLength": 1}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self.paginator

    def delete_objects(self, Bucket, Delete):
        self.deleted.append({"Bucket": Bucket, "Delete": Delete})


def test_save_package_uploads_files_with_content_types(tmp_path):
    passport_json = tmp_path / "passport.json"
    passport_html = tmp_path / "passport.html"
    image = tmp_path / "product_image.jpg"

    passport_json.write_text("{}", encoding="utf-8")
    passport_html.write_text("<html></html>", encoding="utf-8")
    image.write_bytes(b"jpg")

    client = _FakeS3Client()
    storage = S3Storage(
        bucket="passportai-demo",
        region="eu-west-1",
        public_base_url="https://cdn.example.com",
        s3_client=client,
    )

    url = storage.save_package(
        "demo",
        {
            "passport.json": passport_json,
            "passport.html": passport_html,
            "product_image.jpg": image,
        },
    )

    assert url == "https://cdn.example.com/passports/demo/passport.html"

    uploads_by_key = {upload["key"]: upload for upload in client.uploads}
    assert uploads_by_key["passports/demo/passport.json"]["ExtraArgs"]["ContentType"] == (
        "application/ld+json; charset=utf-8"
    )
    assert uploads_by_key["passports/demo/passport.html"]["ExtraArgs"]["ContentType"] == (
        "text/html; charset=utf-8"
    )
    assert uploads_by_key["passports/demo/product_image.jpg"]["ExtraArgs"]["ContentType"] == "image/jpeg"

    assert uploads_by_key["passports/demo/passport.html"]["ExtraArgs"]["CacheControl"] == "no-cache"
    assert "ACL" not in uploads_by_key["passports/demo/passport.html"]["ExtraArgs"]


def test_public_url_falls_back_to_regional_s3_url():
    storage = S3Storage(
        bucket="passportai-demo",
        region="eu-west-1",
        s3_client=_FakeS3Client(),
    )

    assert storage.get_public_url("demo", "passport.html") == (
        "https://passportai-demo.s3.eu-west-1.amazonaws.com/passports/demo/passport.html"
    )


def test_custom_prefix_is_used_for_object_keys(tmp_path):
    passport_html = tmp_path / "passport.html"
    passport_html.write_text("<html></html>", encoding="utf-8")

    client = _FakeS3Client()
    storage = S3Storage(
        bucket="passportai-demo",
        region="eu-west-1",
        public_base_url="https://cdn.example.com",
        prefix="dpp-packages",
        s3_client=client,
    )

    storage.save_package("demo", {"passport.html": passport_html})

    assert client.uploads[0]["key"] == "dpp-packages/demo/passport.html"
    assert storage.get_public_url("demo", "passport.html") == (
        "https://cdn.example.com/dpp-packages/demo/passport.html"
    )


def test_file_exists_uses_head_object(tmp_path):
    passport_html = tmp_path / "passport.html"
    passport_html.write_text("<html></html>", encoding="utf-8")

    client = _FakeS3Client()
    storage = S3Storage(bucket="passportai-demo", s3_client=client)

    storage.save_package("demo", {"passport.html": passport_html})

    assert storage.file_exists("demo", "passport.html") is True
    assert storage.file_exists("demo", "missing.html") is False


def test_delete_package_deletes_all_objects_under_prefix():
    client = _FakeS3Client()
    storage = S3Storage(bucket="passportai-demo", s3_client=client)

    storage.delete_package("demo")

    assert client.paginator.calls == [
        {"Bucket": "passportai-demo", "Prefix": "passports/demo/"}
    ]
    assert client.deleted == [
        {
            "Bucket": "passportai-demo",
            "Delete": {
                "Objects": [
                    {"Key": "passports/demo/passport.html"},
                    {"Key": "passports/demo/passport.json"},
                ],
                "Quiet": True,
            },
        }
    ]


def test_missing_source_file_raises_storage_error(tmp_path):
    storage = S3Storage(bucket="passportai-demo", s3_client=_FakeS3Client())

    with pytest.raises(StorageError, match="Source file not found"):
        storage.save_package("demo", {"passport.html": tmp_path / "missing.html"})


def test_empty_bucket_config_fails_closed(monkeypatch):
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)

    with pytest.raises(ValueError, match="AWS_S3_BUCKET"):
        S3Storage(s3_client=_FakeS3Client())
