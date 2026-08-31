"""Video utility helpers — FFmpeg detection and video metadata."""

import shutil
import subprocess
from typing import Optional


def find_ffmpeg() -> Optional[str]:
    """Return the path to the ffmpeg binary, or None if not found."""
    path = shutil.which("ffmpeg")
    return path


def is_ffmpeg_available() -> bool:
    """Return True if ffmpeg is on PATH and executable."""
    return find_ffmpeg() is not None


def get_video_info(video_path: str) -> dict:
    """Return basic metadata for a video file using ffprobe.

    Returns dict with keys: width, height, fps, duration_s, nb_frames, has_audio.
    Returns empty dict on failure.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {}

        import json
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video_stream = next(
            (s for s in streams if s.get("codec_type") == "video"), None
        )
        if not video_stream:
            return {}

        # Parse FPS from avg_frame_rate (e.g. "30000/1001")
        fps_str = video_stream.get("avg_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 0
        except (ValueError, ZeroDivisionError):
            fps = 0

        # Duration
        fmt = data.get("format", {})
        duration_s = float(fmt.get("duration", 0))

        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": round(fps, 3),
            "duration_s": round(duration_s, 2),
            "nb_frames": int(video_stream.get("nb_frames", 0)),
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        }
    except Exception:
        return {}


def format_duration(seconds: float) -> str:
    """Format seconds into M:SS or H:MM:SS."""
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"
