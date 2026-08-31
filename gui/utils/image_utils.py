"""Image utility helpers — thumbnail generation, format detection, clipboard."""

import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

# Formats accepted by cv2.imread and the GUI file dialogs
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm"}
ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

THUMBNAIL_MAX_PX = 2048  # Longest edge cap for preview thumbnails


def is_image_file(path: str | Path) -> bool:
    """Return True if *path* has an image extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def is_video_file(path: str | Path) -> bool:
    """Return True if *path* has a video extension."""
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def is_supported_file(path: str | Path) -> bool:
    """Return True if *path* is a supported image or video."""
    return Path(path).suffix.lower() in ALL_EXTENSIONS


def get_image_info(path: str | Path) -> dict:
    """Return basic metadata for an image file.

    Returns dict with keys: width, height, mode, format, size_bytes.
    """
    p = Path(path)
    info: dict = {"path": str(p), "size_bytes": p.stat().st_size}
    try:
        with Image.open(p) as img:
            info["width"] = img.width
            info["height"] = img.height
            info["mode"] = img.mode  # "RGB", "RGBA", "L", etc.
            info["format"] = img.format  # "JPEG", "PNG", …
    except Exception:
        info["width"] = 0
        info["height"] = 0
        info["mode"] = "unknown"
        info["format"] = "unknown"
    return info


def generate_thumbnail(
    path: str | Path,
    max_size: int = THUMBNAIL_MAX_PX,
) -> Optional[Image.Image]:
    """Open an image and return a PIL.Image thumbnail (RGB).

    The longest edge is capped at *max_size* px while preserving aspect
    ratio.  Returns ``None`` if the file can't be read.
    """
    try:
        img = Image.open(path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        if img.mode == "RGBA":
            # Composite onto white background for preview
            bg = Image.new("RGB", img.size, (30, 30, 30))
            bg.paste(img, mask=img.split()[3])
            return bg
        return img.convert("RGB")
    except Exception:
        return None


def format_file_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


def format_dimensions(width: int, height: int) -> str:
    """Format dimensions like '1920 × 1080'."""
    return f"{width} × {height}"
