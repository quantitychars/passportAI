from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from src.storage.base import StorageError, StorageProvider


_CONTENT_TYPE_OVERRIDES = {
    "passport.json": "application/ld+json; charset=utf-8",
    "passport.html": "text/html; charset=utf-8",
    "gap_report.html": "text/html; charset=utf-8",
    "qr.png": "image/png",
    "product_image.jpg": "image/jpeg",
    "product_image.jpeg": "image/jpeg",
    "product_image.png": "image/png",
}


class S3Storage(StorageProvider):
    """AWS S3 storage provider for PassportAI artifact packages.

    This provider uploads already-generated local artifacts to S3 and returns
    stable public URLs. It does not generate artifacts and does not decide
    passport readiness.

    Configuration:
        AWS_S3_BUCKET       required, unless bucket=... is passed
        AWS_REGION          default: eu-west-1
        PUBLIC_BASE_URL     optional CloudFront/custom-domain base URL
        AWS_ENDPOINT_URL    optional MinIO/localstack endpoint
        AWS_S3_PREFIX       optional key prefix, default: passports
        AWS_S3_ACL          optional; empty by default. Prefer bucket policy.
    """

    def __init__(
        self,
        *,
        bucket: str | None = None,
        region: str | None = None,
        public_base_url: str | None = None,
        endpoint_url: str | None = None,
        prefix: str | None = None,
        s3_client: Any | None = None,
        acl: str | None = None,
    ) -> None:
        self.bucket = (bucket or os.getenv("AWS_S3_BUCKET", "")).strip()
        self.region = (region or os.getenv("AWS_REGION", "eu-west-1")).strip()
        self.endpoint_url = endpoint_url or os.getenv("AWS_ENDPOINT_URL") or None
        self.prefix = self._normalize_prefix(prefix or os.getenv("AWS_S3_PREFIX", "passports"))

        configured_public_base_url = (
            public_base_url
            or os.getenv("PUBLIC_BASE_URL")
            or os.getenv("S3_PUBLIC_BASE_URL")
            or self._safe_legacy_hosting_url()
            or ""
        )
        self.public_base_url = configured_public_base_url.rstrip("/")

        configured_acl = acl if acl is not None else os.getenv("AWS_S3_ACL", "")
        self.acl = configured_acl.strip() or None

        if not self.bucket:
            raise ValueError("AWS_S3_BUCKET must be set for S3Storage")

        if s3_client is not None:
            self._s3 = s3_client
            return

        try:
            import boto3
        except ImportError as exc:
            raise ValueError(
                "boto3 is required for S3Storage. Install dependencies with: "
                "pip install -r requirements.txt"
            ) from exc

        self._s3 = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
        )

    def save_package(
        self,
        passport_id: str,
        files: dict[str, Path],
    ) -> str:
        """Upload the generated DPP artifact package to S3.

        Args:
            passport_id: Passport package identifier used in the S3 key prefix.
            files: Mapping from package filename to local source path.

        Returns:
            Public URL for passport.html when present; otherwise package base URL.

        Raises:
            StorageError: If any local file is missing or an upload fails.
        """
        if not files:
            raise StorageError("No files were provided for S3 package upload.")

        for filename, source_path in files.items():
            self._upload_file(
                passport_id=passport_id,
                filename=filename,
                source_path=Path(source_path),
            )

        if "passport.html" in files:
            return self.get_public_url(passport_id, "passport.html")

        return self.get_package_url(passport_id)

    def get_public_url(self, passport_id: str, filename: str) -> str:
        """Build a public URL for a specific file in a passport package."""
        key = self._object_key(passport_id, filename)

        if self.public_base_url:
            return f"{self.public_base_url}/{key}"

        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def get_package_url(self, passport_id: str) -> str:
        """Build a public URL for the package directory/prefix."""
        key_prefix = self._object_key(passport_id, "").rstrip("/")

        if self.public_base_url:
            return f"{self.public_base_url}/{key_prefix}"

        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key_prefix}"

    def file_exists(self, passport_id: str, filename: str) -> bool:
        """Return True if the S3 object exists."""
        key = self._object_key(passport_id, filename)
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            if self._is_not_found_error(exc):
                return False
            raise StorageError(f"S3 head_object failed for {key}: {exc}") from exc

    def delete_package(self, passport_id: str) -> None:
        """Delete all objects under this passport package prefix."""
        prefix = f"{self._object_key(passport_id, '')}/"
        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                objects = [
                    {"Key": item["Key"]}
                    for item in page.get("Contents", [])
                    if isinstance(item, dict) and item.get("Key")
                ]

                for index in range(0, len(objects), 1000):
                    chunk = objects[index : index + 1000]
                    if chunk:
                        self._s3.delete_objects(
                            Bucket=self.bucket,
                            Delete={"Objects": chunk, "Quiet": True},
                        )
        except Exception as exc:
            raise StorageError(f"Failed to delete S3 package {passport_id}: {exc}") from exc

    def _upload_file(
        self,
        *,
        passport_id: str,
        filename: str,
        source_path: Path,
    ) -> None:
        if not source_path.exists():
            raise StorageError(f"Source file not found: {source_path}")

        if not source_path.is_file():
            raise StorageError(f"Source path is not a file: {source_path}")

        key = self._object_key(passport_id, filename)
        extra_args = {
            "ContentType": self._content_type(filename),
            "CacheControl": self._cache_control(filename),
        }

        if self.acl:
            extra_args["ACL"] = self.acl

        try:
            self._s3.upload_file(
                str(source_path),
                self.bucket,
                key,
                ExtraArgs=extra_args,
            )
        except Exception as exc:
            raise StorageError(f"S3 upload failed for {filename}: {exc}") from exc

    def _object_key(self, passport_id: str, filename: str) -> str:
        clean_passport_id = self._clean_key_part(passport_id)
        clean_filename = filename.replace("\\", "/").strip("/")

        if not clean_passport_id:
            raise ValueError("passport_id must not be empty")

        parts = [part for part in (self.prefix, clean_passport_id, clean_filename) if part]
        return "/".join(parts)

    def _content_type(self, filename: str) -> str:
        normalized = filename.replace("\\", "/").split("/")[-1].lower()

        if normalized in _CONTENT_TYPE_OVERRIDES:
            return _CONTENT_TYPE_OVERRIDES[normalized]

        guessed, _ = mimetypes.guess_type(normalized)
        return guessed or "application/octet-stream"

    def _cache_control(self, filename: str) -> str:
        normalized = filename.replace("\\", "/").split("/")[-1].lower()

        if normalized.endswith(".html") or normalized.endswith(".json"):
            return "no-cache"

        if normalized.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
            return "public, max-age=31536000, immutable"

        return "no-cache"

    def _is_not_found_error(self, exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error = response.get("Error", {})
            code = str(error.get("Code", "")).lower()
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            return code in {"404", "notfound", "nosuchkey"} or status == 404

        message = str(exc).lower()
        return "not found" in message or "404" in message or "nosuchkey" in message

    def _safe_legacy_hosting_url(self) -> str:
        """Use HOSTING_URL only when it is not the local development default."""
        value = os.getenv("HOSTING_URL", "").strip().rstrip("/")
        if not value:
            return ""

        lowered = value.lower()
        if "localhost" in lowered or "127.0.0.1" in lowered:
            return ""

        return value

    def _normalize_prefix(self, value: str) -> str:
        return value.replace("\\", "/").strip("/")

    def _clean_key_part(self, value: str) -> str:
        return str(value).replace("\\", "/").strip("/")
