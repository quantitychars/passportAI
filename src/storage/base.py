"""
src/storage/base.py — Abstract Storage Provider Interface

Defines the contract for all storage backends (local filesystem, AWS S3, etc.).

Both LocalStorage and S3Storage implement this interface.
The storage mode is selected via STORAGE_MODE env var ("local" | "s3").

Usage:
    from src.storage.base import StorageProvider
    # Use LocalStorage or S3Storage — both implement this interface
"""

from abc import ABC, abstractmethod
from pathlib import Path


class StorageProvider(ABC):
    """Abstract base class for DPP package storage backends.

    All storage implementations must provide:
      - save_package: Save all DPP files and return the public URL
      - get_public_url: Build public URL for a given file
      - file_exists: Check if a file exists in storage
      - delete_package: Remove all files for a passport ID

    The passport_url returned by save_package() is used to:
      1. Build the QR code (step 13 — ALWAYS LAST)
      2. Populate the JSON-LD passport's photo.url field
      3. Provide URLs used by the rendered passport and QR code

    Notes:
        - Never hardcode S3 bucket names or local paths. Use env vars.
        - All Path parameters use pathlib.Path, never str paths.
        - All implementations must be thread-safe for concurrent generation.
    """

    @abstractmethod
    def save_package(
        self,
        passport_id: str,
        files: dict[str, Path],
    ) -> str:
        """Save all DPP package files and return the passport's public URL.

        This method is called BEFORE generate_qr() — the returned URL
        is used to encode the QR code.

        Args:
            passport_id: UUID of the passport (used as directory/prefix).
            files: Dictionary mapping filenames to local file paths.
                   Expected keys: "passport.json", "photo.png", "passport.html",
                                  "gap_report.html"
                   QR code (qr.png) is added AFTER this call returns.

        Returns:
            Public URL for accessing the passport HTML page or local package base URL (e.g., "http://localhost:7860/{uuid}"
            or "https://bucket.s3.amazonaws.com/{uuid}/passport.json").

        Raises:
            StorageError: If any file fails to save.

        Example:
            >>> provider = LocalStorage(output_dir="./output", hosting_url="http://localhost:7860")
            >>> url = provider.save_package("abc-123", {"passport.json": Path("tmp/passport.json")})
            >>> print(url)  # "http://localhost:7860/abc-123"
        """
        ...

    @abstractmethod
    def get_public_url(self, passport_id: str, filename: str) -> str:
        """Build the public URL for a specific file in a passport package.

        Args:
            passport_id: UUID of the passport.
            filename: Name of the file (e.g., "photo.png", "passport.json").

        Returns:
            Full public URL string.

        Example:
            >>> url = provider.get_public_url("abc-123", "photo.png")
            >>> print(url)  # "http://localhost:7860/abc-123/photo"
        """
        ...

    @abstractmethod
    def file_exists(self, passport_id: str, filename: str) -> bool:
        """Check if a file exists in storage.

        Args:
            passport_id: UUID of the passport.
            filename: Name of the file to check.

        Returns:
            True if the file exists, False otherwise.
        """
        ...

    @abstractmethod
    def delete_package(self, passport_id: str) -> None:
        """Delete all files associated with a passport ID.

        Args:
            passport_id: UUID of the passport to delete.

        Raises:
            StorageError: If deletion fails.
        """
        ...

    def save_qr(self, passport_id: str, qr_path: Path) -> str:
        """Save the QR code file. Called LAST in the pipeline.

        Convenience method that calls save_package() with just the QR file.

        Args:
            passport_id: UUID of the passport.
            qr_path: Path to the generated qr.png file.

        Returns:
            Public URL for the QR code file.
        """
        # Default: delegate to save_package
        return self.save_package(passport_id, {"qr.png": qr_path})


class StorageError(Exception):
    """Raised when a storage operation fails."""
    pass
