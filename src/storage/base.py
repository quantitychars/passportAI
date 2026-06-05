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
      - save_package: Save the selected DPP artifacts and return the passport URL
      - get_public_url: Build a public URL for a given file
      - file_exists: Check whether a file exists in storage
      - delete_package: Remove files for a passport ID

    The pipeline owns artifact selection:
      - LocalStorage receives the full local review/download package.
      - S3Storage receives only passport.html; the ZIP and full package remain local.

    Notes:
        - Never hardcode S3 bucket names or local paths. Use env vars.
        - All Path parameters use pathlib.Path, never str paths.
        - QR codes point to passport.html, not to a legal certification endpoint.
    """

    @abstractmethod
    def save_package(
        self,
        passport_id: str,
        files: dict[str, Path],
    ) -> str:
        """Save selected DPP artifacts and return the passport URL.

        PassportPipeline calls this after local artifacts are generated. The
        ``files`` mapping is intentionally backend-dependent: local mode stores
        the full package, while S3 mode stores only ``passport.html``.

        Args:
            passport_id: UUID of the passport, used as directory or object prefix.
            files: Mapping of target filenames to local file paths. Current
                artifacts may include ``passport.json``, ``passport.html``,
                ``gap_report.html``, ``qr.png``, ``product_image.<ext>``, and
                ``passport_package.zip``. Upload-only backends may receive a
                deliberate subset.

        Returns:
            Public URL for the passport HTML page or local package base URL.

        Raises:
            StorageError: If any selected file fails to save.
        """
        ...

    @abstractmethod
    def get_public_url(self, passport_id: str, filename: str) -> str:
        """Build the public URL for a specific file in a passport package.

        Args:
            passport_id: UUID of the passport.
            filename: Name of the file (e.g., "product_image.png", "passport.html").

        Returns:
            Full public URL string.

        Example:
            >>> url = provider.get_public_url("abc-123", "passport.html")
            >>> print(url)  # "http://localhost:7860/abc-123/passport.html"
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
        """Save a QR code file through the storage backend.

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
