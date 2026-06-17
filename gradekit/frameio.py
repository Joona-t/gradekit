"""frameio.py — get a single frame into a float RGB array, and write images back out.

The ONLY external process gradekit ever spawns is ffmpeg/ffprobe, and only for video
inputs. Images are read directly with Pillow. There is no network access anywhere.

A note on color accuracy (honest limitation): when ffmpeg decodes a compressed video it
performs a YUV -> RGB conversion that depends on the clip's color matrix (BT.709 vs 601)
and range (limited "TV" vs full "PC"). We let ffmpeg apply its sensible defaults and ask
for plain rgb24 output. For the *relative* diagnosis gradekit does (is it warm? is it
clipping?) this is robust, but absolute Kelvin numbers from exotic footage may drift.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".m2ts", ".mts"}


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def is_image(path: str) -> bool:
    return _ext(path) in IMAGE_EXTS


def is_video(path: str) -> bool:
    return _ext(path) in VIDEO_EXTS


def load_image_rgb(path: str) -> np.ndarray:
    """Read an image to a float64 RGB array in [0, 1], shape (H, W, 3).

    `.convert("RGB")` normalizes every input mode for us: it drops alpha (RGBA), expands
    palette/indexed images, and replicates grayscale into three channels.
    """
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float64) / 255.0
    return arr


def ffprobe_duration(path: str):
    """Return clip duration in seconds, or None if ffprobe is missing/unhelpful."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        dur = data.get("format", {}).get("duration")
        return float(dur) if dur is not None else None
    except Exception:
        return None


def extract_frame(path: str, t: float | None = None):
    """Extract one frame from a video to a float RGB array. Returns (array, used_timestamp).

    Timestamp policy: use --t if given, else ~10% into the clip (a "representative" frame
    that skips slates/black at the head), else 1.0s if the duration is unknown.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH — it is required to read video frames.")

    if t is None:
        dur = ffprobe_duration(path)
        t = (dur * 0.10) if dur else 1.0

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        # -ss BEFORE -i seeks fast (keyframe-accurate is plenty for a representative frame).
        # -frames:v 1 grabs exactly one frame; -pix_fmt rgb24 gives us clean 8-bit RGB.
        cmd = ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", path,
               "-frames:v", "1", "-pix_fmt", "rgb24", tmp.name]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0 or os.path.getsize(tmp.name) == 0:
            # The seek may have overshot a very short clip — retry from the start.
            cmd2 = ["ffmpeg", "-y", "-i", path,
                    "-frames:v", "1", "-pix_fmt", "rgb24", tmp.name]
            proc2 = subprocess.run(cmd2, capture_output=True, text=True)
            if proc2.returncode != 0 or os.path.getsize(tmp.name) == 0:
                tail = (proc.stderr or proc2.stderr or "")[-600:]
                raise RuntimeError(f"ffmpeg could not extract a frame:\n{tail}")
            t = 0.0
        return load_image_rgb(tmp.name), t
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def load_frame(path: str, t: float | None = None):
    """Return (rgb01 array HxWx3, info dict). Decides image vs video by extension,
    falling back to trying both if the extension is unfamiliar."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"input not found: {path}")

    if is_image(path):
        return load_image_rgb(path), {"kind": "image", "t": None}
    if is_video(path):
        arr, used_t = extract_frame(path, t)
        return arr, {"kind": "video", "t": used_t}

    # Unknown extension: try as image, then as video.
    try:
        return load_image_rgb(path), {"kind": "image", "t": None}
    except Exception:
        arr, used_t = extract_frame(path, t)
        return arr, {"kind": "video", "t": used_t}


def crop_region(arr: np.ndarray, region) -> np.ndarray:
    """Crop (x, y, w, h) in pixels, clamped to image bounds. Raises if the result is empty."""
    H, W = arr.shape[:2]
    x, y, w, h = (int(v) for v in region)
    x0 = max(0, min(x, W - 1))
    y0 = max(0, min(y, H - 1))
    x1 = max(x0 + 1, min(x + w, W))
    y1 = max(y0 + 1, min(y + h, H))
    patch = arr[y0:y1, x0:x1]
    if patch.size == 0:
        raise ValueError(f"region {tuple(region)} is empty after clamping to {W}x{H}")
    return patch


def save_image_rgb(path: str, arr01: np.ndarray) -> None:
    """Write a float [0,1] RGB array to an 8-bit image (rounding, not truncating)."""
    u8 = (np.clip(arr01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(u8, "RGB").save(path)


def save_side_by_side(path: str, before01: np.ndarray, after01: np.ndarray) -> None:
    """Write a before|after PNG with a thin white separator between the two halves."""
    H = before01.shape[0]
    separator = np.ones((H, 8, 3), dtype=np.float64)
    combo = np.concatenate([before01, separator, after01], axis=1)
    save_image_rgb(path, combo)
