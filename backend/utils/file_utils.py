"""
File handling utilities.
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Optional


def get_file_hash(file_path: Path, algorithm: str = "md5") -> str:
    """
    Calculate file hash.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)

    Returns:
        Hex digest of file hash
    """
    hash_func = getattr(hashlib, algorithm)()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_file_mime_type(file_path: Path) -> Optional[str]:
    """
    Get MIME type of file.

    Args:
        file_path: Path to file

    Returns:
        MIME type string or None if unknown
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0

    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def ensure_directory(directory: Path) -> Path:
    """
    Ensure directory exists, create if necessary.

    Args:
        directory: Directory path

    Returns:
        Path to directory
    """
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Create a safe filename by removing/replacing problematic characters.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Safe filename
    """
    import re

    # Remove or replace problematic characters
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove leading/trailing whitespace and dots
    safe_name = safe_name.strip(" .")

    # Truncate if too long
    if len(safe_name) > max_length:
        name_part, ext = safe_name.rsplit(".", 1) if "." in safe_name else (safe_name, "")
        max_name_length = max_length - len(ext) - 1 if ext else max_length
        safe_name = name_part[:max_name_length] + ("." + ext if ext else "")

    return safe_name or "unnamed_file"
