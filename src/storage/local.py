"""
src/storage/local.py — Local Filesystem Storage Provider

Saves DPP package files to the local output/ directory and
serves them via FastAPI on localhost.

Directory structure:
    output/{passport_id}/
        passport.json
        photo.png
        passport.html
        gap_report.pdf
        qr.png              ← saved last

Public URLs use the HOSTING_URL env var as base:
    http://localhost:8000/{passport_id}
    http://localhost:8000/{passport_id}/photo
    http://localhost:8000/{passport_id}/html

Usage:
    from src.storage.local import LocalStorage
    storage = LocalStorage()  # reads from env vars
    url = storage.save_package("abc-123", {"passport.json": Path("tmp/p.json")})
"""

import os
import shutil
from pathlib import Path

from src.storage.base import StorageError, StorageProvider


class LocalStorage(StorageProvider):
    """Local filesystem storage provider.

    Copies DPP package files to output/{passport_id}/ directory.
    Generates public URLs using the configured HOSTING_URL.

    Attributes:
        output_dir: Base directory for all passport packages.
        hosting_url: Base URL for serving files (e.g., "http://localhost:8000").
    """

    def __init__(
        self,
        output_dir: str | Path | None = None,
        hosting_url: str | None = None,
    ) -> None:
        """Initialize LocalStorage.

        Args:
            output_dir: Directory for storing packages. Defaults to LOCAL_OUTPUT_DIR
                        env var or "./output".
            hosting_url: Base URL. Defaults to HOSTING_URL env var or
                         "http://localhost:8000".
        """
        self.output_dir = Path(
            output_dir or os.getenv("LOCAL_OUTPUT_DIR", "./output")
        )
        self.hosting_url = (
            hosting_url or os.getenv("HOSTING_URL", "http://localhost:8000")
        ).rstrip("/")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_package(
        self,
        passport_id: str,
        files: dict[str, Path],
    ) -> str:
        """Copy package files to output/{passport_id}/ directory.

        Args:
            passport_id: UUID of the passport.
            files: Dict mapping target filename to source Path.

        Returns:
            Base URL for the passport: "{hosting_url}/{passport_id}"

        Raises:
            StorageError: If any file copy fails.

        Example:
            >>> storage = LocalStorage()
            >>> url = storage.save_package("abc-123", {"passport.json": Path("tmp/p.json")})
            >>> # Files now at: output/abc-123/passport.json
            >>> print(url)  # "http://localhost:8000/abc-123"
        """
        package_dir = self.output_dir / passport_id
        package_dir.mkdir(parents=True, exist_ok=True)

        for filename, source_path in files.items():
            source_path = Path(source_path)
            if not source_path.exists():
                raise StorageError(f"Source file not found: {source_path}")

            destination = package_dir / filename
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source_path.resolve() != destination.resolve():
                    shutil.copy2(str(source_path), str(destination))
            except OSError as exc:
                raise StorageError(f"Failed to copy {filename}: {exc}") from exc

        return f"{self.hosting_url}/{passport_id}"

    def get_public_url(self, passport_id: str, filename: str) -> str:
        """Build public URL for a specific file.

        Args:
            passport_id: UUID of the passport.
            filename: File name (e.g., "photo.png", "passport.json").

        Returns:
            Full public URL string.

        Example:
            >>> url = storage.get_public_url("abc-123", "photo.png")
            >>> print(url)  # "http://localhost:8000/abc-123/photo"
        """
        # Map filenames to clean API routes
        route_map = {
            "passport.json": "",
            "photo.png": "/photo",
            "passport.html": "/html",
            "gap_report.html": "/gap-report",
            "gap_report.pdf": "/gap-report",
            "qr.png": "/qr",
        }
        suffix = route_map.get(filename, f"/{filename}")
        return f"{self.hosting_url}/{passport_id}{suffix}"

    def file_exists(self, passport_id: str, filename: str) -> bool:
        """Check if a file exists in the local output directory.

        Args:
            passport_id: UUID of the passport.
            filename: File name to check.

        Returns:
            True if the file exists at output/{passport_id}/{filename}.
        """
        return (self.output_dir / passport_id / filename).exists()

    def delete_package(self, passport_id: str) -> None:
        """Delete all files for a passport package.

        Args:
            passport_id: UUID of the passport to delete.

        Raises:
            StorageError: If deletion fails.
        """
        package_dir = self.output_dir / passport_id
        if package_dir.exists():
            try:
                shutil.rmtree(str(package_dir))
            except OSError as exc:
                raise StorageError(f"Failed to delete package {passport_id}: {exc}") from exc

    def get_package_dir(self, passport_id: str) -> Path:
        """Get the local directory path for a passport package.

        Args:
            passport_id: UUID of the passport.

        Returns:
            Path to output/{passport_id}/ directory.
        """
        return self.output_dir / passport_id


if __name__ == "__main__":
    storage = LocalStorage()
    print(f"Output directory: {storage.output_dir.absolute()}")
    print(f"Hosting URL:      {storage.hosting_url}")
    print(f"Sample URL:       {storage.get_public_url('test-uuid-123', 'passport.json')}")
