"""
src/storage/aws_s3.py — AWS S3 Storage Provider

Uploads DPP package files to an S3 bucket in eu-west-1 region.
Files are publicly accessible via S3 URLs or CloudFront.

S3 key structure:
    {passport_id}/passport.json
    {passport_id}/photo.png
    {passport_id}/passport.html
    {passport_id}/gap_report.pdf
    {passport_id}/qr.png          ← uploaded last

Required IAM permissions:
    s3:PutObject
    s3:GetObject
    s3:DeleteObject
    s3:ListBucket

Usage:
    from src.storage.aws_s3 import S3Storage
    storage = S3Storage()  # reads from env vars
    url = storage.save_package("abc-123", {"passport.json": Path("tmp/p.json")})
"""

import os
from pathlib import Path

from src.storage.base import StorageError, StorageProvider


class S3Storage(StorageProvider):
    """AWS S3 storage provider for DPP packages.

    Uploads files to S3 and returns public URLs.
    Configured via environment variables (see .env.example).

    Attributes:
        bucket: S3 bucket name.
        region: AWS region (should be eu-west-1 for GDPR compliance).
        hosting_url: Custom base URL (optional, for CloudFront or custom domain).
    """

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        hosting_url: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize S3Storage.

        Args:
            bucket: S3 bucket name. Defaults to AWS_S3_BUCKET env var.
            region: AWS region. Defaults to AWS_REGION env var or "eu-west-1".
            hosting_url: Custom public URL base. Defaults to HOSTING_URL env var.
                         If not set, uses the S3 bucket URL directly.
            endpoint_url: Custom S3 endpoint (for MinIO or localstack testing).
                          Defaults to AWS_ENDPOINT_URL env var.
        """
        self.bucket = bucket or os.getenv("AWS_S3_BUCKET", "")
        self.region = region or os.getenv("AWS_REGION", "eu-west-1")
        self.hosting_url = (
            hosting_url or os.getenv("HOSTING_URL", "")
        ).rstrip("/")
        self.endpoint_url = endpoint_url or os.getenv("AWS_ENDPOINT_URL") or None

        if not self.bucket:
            raise ValueError("AWS_S3_BUCKET must be set for S3Storage")

        # TODO: initialize boto3 client
        # import boto3
        # self._s3 = boto3.client(
        #     "s3",
        #     region_name=self.region,
        #     endpoint_url=self.endpoint_url,
        # )
        self._s3 = None  # Replace with real boto3 client

    def save_package(
        self,
        passport_id: str,
        files: dict[str, Path],
    ) -> str:
        """Upload DPP package files to S3.

        Args:
            passport_id: UUID of the passport (used as S3 key prefix).
            files: Dict mapping target filename to local source Path.

        Returns:
            Public base URL for the passport.
            If hosting_url is set: "{hosting_url}/{passport_id}"
            Otherwise: "https://{bucket}.s3.{region}.amazonaws.com/{passport_id}"

        Raises:
            StorageError: If any file upload fails.
            ValueError: If S3 client is not initialized.

        Example:
            >>> storage = S3Storage()
            >>> url = storage.save_package("abc-123", {"passport.json": Path("tmp/p.json")})
            >>> print(url)  # "https://passportai-passports.s3.eu-west-1.amazonaws.com/abc-123"
        """
        if self._s3 is None:
            raise ValueError("boto3 client not initialized. Implement S3Storage.__init__ first.")

        # TODO: implement S3 upload
        # content_type_map = {
        #     "passport.json": "application/ld+json",
        #     "photo.png": "image/png",
        #     "passport.html": "text/html; charset=utf-8",
        #     "gap_report.pdf": "application/pdf",
        #     "qr.png": "image/png",
        # }
        # for filename, source_path in files.items():
        #     source_path = Path(source_path)
        #     if not source_path.exists():
        #         raise StorageError(f"Source file not found: {source_path}")
        #     s3_key = f"{passport_id}/{filename}"
        #     content_type = content_type_map.get(filename, "application/octet-stream")
        #     try:
        #         self._s3.upload_file(
        #             str(source_path),
        #             self.bucket,
        #             s3_key,
        #             ExtraArgs={
        #                 "ContentType": content_type,
        #                 "ACL": "public-read",
        #             },
        #         )
        #     except Exception as e:
        #         raise StorageError(f"S3 upload failed for {filename}: {e}") from e
        #
        # if self.hosting_url:
        #     return f"{self.hosting_url}/{passport_id}"
        # return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{passport_id}"
        raise NotImplementedError("S3Storage.save_package() not yet implemented")

    def get_public_url(self, passport_id: str, filename: str) -> str:
        """Build the public S3 URL for a specific file.

        Args:
            passport_id: UUID of the passport.
            filename: File name (e.g., "passport.json").

        Returns:
            Full public URL for the file on S3.
        """
        s3_key = f"{passport_id}/{filename}"
        if self.hosting_url:
            return f"{self.hosting_url}/{s3_key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key}"

    def file_exists(self, passport_id: str, filename: str) -> bool:
        """Check if a file exists in S3.

        Args:
            passport_id: UUID of the passport.
            filename: File name to check.

        Returns:
            True if the object exists in S3.
        """
        # TODO: implement using head_object
        # try:
        #     self._s3.head_object(Bucket=self.bucket, Key=f"{passport_id}/{filename}")
        #     return True
        # except self._s3.exceptions.ClientError:
        #     return False
        raise NotImplementedError("S3Storage.file_exists() not yet implemented")

    def delete_package(self, passport_id: str) -> None:
        """Delete all S3 objects with the passport_id prefix.

        Args:
            passport_id: UUID of the passport to delete.

        Raises:
            StorageError: If deletion fails.
        """
        # TODO: implement S3 batch delete
        # response = self._s3.list_objects_v2(Bucket=self.bucket, Prefix=f"{passport_id}/")
        # objects = [{"Key": obj["Key"]} for obj in response.get("Contents", [])]
        # if objects:
        #     self._s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
        raise NotImplementedError("S3Storage.delete_package() not yet implemented")
