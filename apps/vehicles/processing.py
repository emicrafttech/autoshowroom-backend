"""Media processing for feed-optimized delivery.

Videos are transcoded to ~720p H.264 (~800 kbps) with faststart so playback
can begin before the full file downloads. Target bitrate is tuned for mobile
cellular feeds (Instagram/TikTok-class progressive delivery without ABR).
Photos are resized to a 1200px max edge and re-encoded as JPEG quality 80.
Video posters are captured at 1s.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

VIDEO_MAX_LONG_EDGE = 1280
VIDEO_MAX_FPS = 30
VIDEO_PROFILE = "main"
VIDEO_LEVEL = "4.0"
VIDEO_CRF = 23
VIDEO_TARGET_BITRATE = "800k"
VIDEO_MAX_BITRATE = "1200k"
VIDEO_BUFFER_SIZE = "2400k"
VIDEO_AUDIO_BITRATE = "96k"

IMAGE_MAX_EDGE = 1200
IMAGE_JPEG_QUALITY = 80

POSTER_TIMESTAMP = "00:00:01.000"


@dataclass(frozen=True)
class ProcessedVideo:
    video_path: Path
    poster_path: Path | None


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def transcode_video(source: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    scale_filter = (
        f"scale='min({VIDEO_MAX_LONG_EDGE},iw)':'min({VIDEO_MAX_LONG_EDGE},ih)':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )
    _run_ffmpeg([
        "-i", str(source),
        "-vf", scale_filter,
        "-fpsmax", str(VIDEO_MAX_FPS),
        "-c:v", "libx264",
        "-profile:v", VIDEO_PROFILE,
        "-level", VIDEO_LEVEL,
        "-preset", "medium",
        "-crf", str(VIDEO_CRF),
        "-b:v", VIDEO_TARGET_BITRATE,
        "-maxrate", VIDEO_MAX_BITRATE,
        "-bufsize", VIDEO_BUFFER_SIZE,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", VIDEO_AUDIO_BITRATE,
        "-movflags", "+faststart",
        str(output),
    ])
    return output


def extract_video_poster(source: Path, output: Path) -> Path | None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run_ffmpeg([
            "-ss", POSTER_TIMESTAMP,
            "-i", str(source),
            "-frames:v", "1",
            "-q:v", "3",
            str(output),
        ])
    except subprocess.CalledProcessError:
        return None
    return output if output.exists() else None


def process_video(source: Path, work_dir: Path) -> ProcessedVideo:
    video_path = transcode_video(source, work_dir / "transcoded.mp4")
    poster_path = extract_video_poster(source, work_dir / "poster.jpg")
    return ProcessedVideo(video_path=video_path, poster_path=poster_path)


def compress_image(source: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        image.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE))
        image.save(output, "JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return output


def make_work_dir(prefix: str = "as_media_") -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_work_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
