"""skin.py — sample a skin region and judge it against a healthy target.

Detection is a graceful fallback chain so the tool NEVER hard-fails on a missing dep:
  1. explicit --skin x,y,w,h               (you tell us exactly where)
  2. OpenCV Haar face cascade              (only if cv2 imports; optional dependency)
  3. pure-numpy YCbCr skin-mask heuristic  (always available, zero extra deps)
  4. give up and return None               (caller prints a "skipped" note)

Healthy skin, across all ethnicities, clusters around hue 20-40 degrees (orange) with
moderate saturation. We measure the sample's hue/saturation and FLAG problems — but we
NEVER bake skin changes into the LUT. Desaturating or hue-shifting skin is a creative
decision, so we leave it to you (e.g. Lumetri's HSL Secondary).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import colorscience as cs

# Healthy skin target band. Hue in degrees; saturation as a fraction.
SKIN_HUE_LO, SKIN_HUE_HI = 20.0, 40.0
SKIN_HUE_HARD_LO = 15.0      # below this = noticeably too red/magenta
SKIN_SAT_MAX = 0.60          # above this = oversaturated for skin


@dataclass
class SkinResult:
    hue: float
    sat: float
    val: float
    method: str
    healthy: bool
    flags: list   # human-readable problem strings (empty if healthy)


def skin_mask_ycbcr(rgb01: np.ndarray) -> np.ndarray:
    """Pure-numpy skin detector. Returns a boolean mask of likely-skin pixels.

    Skin tone is famously compact in chroma (Cb/Cr) even though it varies a lot in
    brightness, which is exactly why this simple, classic YCbCr box works across skin
    tones. The Cb/Cr ranges below are the widely-used Hsu/Chai-Ngan thresholds.
    """
    rgb = np.clip(rgb01, 0.0, 1.0) * 255.0
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # BT.601 full-range RGB -> YCbCr (the standard JPEG matrix).
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cb = 128.0 - 0.168736 * R - 0.331264 * G + 0.5 * B
    Cr = 128.0 + 0.5 * R - 0.418688 * G - 0.081312 * B
    return (Cb >= 77) & (Cb <= 127) & (Cr >= 133) & (Cr <= 173) & (Y > 40)


def _detect_face_cv2(rgb01: np.ndarray):
    """Try an OpenCV Haar frontal-face detection. Returns a (x,y,w,h) sub-rect of the
    cheeks/nose, or None on any failure (cv2 missing, cascade missing, no face)."""
    try:
        import cv2  # optional dependency — guarded so its absence is never fatal
    except Exception:
        return None
    try:
        img_u8 = (np.clip(rgb01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        gray = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        clf = cv2.CascadeClassifier(cascade_path)
        if clf.empty():
            return None
        faces = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])   # largest face
        # Sample the mid-face (cheeks/nose) to dodge hair, eyes, and background.
        return (int(x + 0.25 * w), int(y + 0.45 * h), int(0.5 * w), int(0.25 * h))
    except Exception:
        return None


def _judge(hue: float, sat: float):
    flags = []
    if hue > SKIN_HUE_HI:
        flags.append(f"hue {hue:.0f}deg is past the healthy band — skin pushed warm/yellow")
    elif hue < SKIN_HUE_HARD_LO:
        flags.append(f"hue {hue:.0f}deg is below the healthy band — skin reads too red/magenta")
    if sat > SKIN_SAT_MAX:
        flags.append(f"saturation {sat * 100:.0f}% is high — skin looks oversaturated")
    return flags


def analyze_skin(rgb01: np.ndarray, region=None):
    """Analyze skin on an ENCODED RGB frame (feed the WB-corrected frame so we judge the
    *graded* skin, not the raw cast). Returns a SkinResult, or None if nothing was found."""
    if region is not None:
        from .frameio import crop_region
        patch = crop_region(rgb01, region).reshape(-1, 3)
        method = "explicit --skin region"
        mean = patch.mean(axis=0)
    else:
        face = _detect_face_cv2(rgb01)
        if face is not None:
            from .frameio import crop_region
            mean = crop_region(rgb01, face).reshape(-1, 3).mean(axis=0)
            method = "auto (OpenCV face)"
        else:
            mask = skin_mask_ycbcr(rgb01)
            if int(mask.sum()) < 50:
                return None   # nothing skin-like; caller prints a skip note
            mean = rgb01[mask].mean(axis=0)
            method = "auto (numpy YCbCr skin heuristic)"

    hsv = cs.rgb_to_hsv(mean.reshape(1, 3))[0]
    hue, sat, val = float(hsv[0]), float(hsv[1]), float(hsv[2])
    flags = _judge(hue, sat)
    return SkinResult(hue=hue, sat=sat, val=val, method=method,
                      healthy=(len(flags) == 0), flags=flags)
