"""whitebalance.py — estimate a per-channel gain that neutralizes a color cast, then
translate that gain into approximate Premiere Lumetri Temperature/Tint numbers.

All averaging happens in LINEAR light (see colorscience.py for the why). A "gain" here is
a single per-channel multiplier applied to linear RGB. This is the diagonal (von Kries)
model of white balance — the same thing your camera's WB and Lumetri's Temp/Tint sliders
are effectively doing: scaling each channel until a neutral object reads neutral.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import colorscience as cs

# Don't let a bad sample produce a wild correction. A 4x gain on one channel is already
# ~2 stops; beyond that we're almost certainly looking at a mis-placed patch, not a cast.
GAIN_MIN, GAIN_MAX = 0.25, 4.0

# Empirical scale factors mapping log-gain ratios onto Lumetri's ~[-100, 100] sliders.
# These are CALIBRATED APPROXIMATIONS. Lumetri's Temp/Tint scale is proprietary and
# non-linear, so treat the reported numbers as a strong starting point, not gospel.
#   Calibration: a ~1.6x blue/red corrective ratio (a clearly warm source) should read
#   about -50 Temperature.  ln(1.6) ~= 0.47, so k ~= 50 / 0.47 ~= 106  ->  round to 100.
K_TEMP = 100.0
K_TINT = 100.0


@dataclass
class WBResult:
    gains: tuple                       # linear per-channel multipliers (r, g, b)
    method: str                        # "neutral-patch" or "gray-world"
    confidence: str                    # "high" (neutral patch) / "low" (gray-world guess)
    lumetri_temp: float                # approx Lumetri Temperature offset
    lumetri_tint: float                # approx Lumetri Tint offset
    patch_rgb_linear: tuple            # measured sample mean (linear), or None
    note: str = ""


def _clamp_gains(gr, gg, gb):
    return (
        float(np.clip(gr, GAIN_MIN, GAIN_MAX)),
        float(np.clip(gg, GAIN_MIN, GAIN_MAX)),
        float(np.clip(gb, GAIN_MIN, GAIN_MAX)),
    )


def gains_from_neutral_patch(patch_linear: np.ndarray):
    """Region we KNOW should read neutral -> gains that make it neutral. Returns (gains, note).

    A neutral surface reflects every wavelength equally, so its linear R, G, B should be
    equal. We choose a target value T equal to the patch's luminance, then scale each
    channel to hit T. Using luminance as the target keeps the patch's BRIGHTNESS fixed, so
    white balance only moves color and doesn't double as an exposure change.
    """
    mean = patch_linear.reshape(-1, 3).mean(axis=0)
    r, g, b = float(mean[0]), float(mean[1]), float(mean[2])

    eps = 1e-5
    note = ""
    if min(r, g, b) < eps:
        note = "neutral patch is nearly black — the WB estimate may be unreliable"

    # Luminance-preserving target: a neutral patch at value T has luminance T, so aiming
    # every channel at T = current luminance leaves brightness untouched.
    target = cs.LUMA_R * r + cs.LUMA_G * g + cs.LUMA_B * b
    target = max(target, eps)
    gains = _clamp_gains(target / max(r, eps), target / max(g, eps), target / max(b, eps))
    return gains, note


def gains_from_gray_world(img_linear: np.ndarray):
    """No neutral patch given -> assume the whole scene averages to gray. Returns (gains, note).

    Gray-world is a classic, robust auto-WB heuristic: if the average of everything in
    frame "should" be neutral, then any imbalance in the channel means IS the cast. It is
    fooled by strongly mono-color scenes (a forest, a sunset), which is why a neutral
    patch always wins when you can give one.
    """
    flat = img_linear.reshape(-1, 3)
    # Exclude near-clipped highlights: a blown sky/spec is a bad color reference.
    luma = cs.luminance_linear(flat)
    keep = luma < 0.95
    if int(keep.sum()) < 16:
        keep = np.ones(flat.shape[0], dtype=bool)

    mean = flat[keep].mean(axis=0)
    r, g, b = float(mean[0]), float(mean[1]), float(mean[2])
    eps = 1e-5
    gray = (r + g + b) / 3.0
    gains = _clamp_gains(gray / max(r, eps), gray / max(g, eps), gray / max(b, eps))
    note = "gray-world guess: assumes the scene average is neutral; can be fooled by a strongly colored scene"
    return gains, note


def gains_to_lumetri(gains):
    """Map corrective linear gains -> approximate Lumetri (Temperature, Tint).

    Temperature axis = blue<->amber. If the fix needs to BOOST BLUE / CUT RED, the source
    was too warm, so the corrective Lumetri move is COOLER => negative Temperature.

    Tint axis = green<->magenta. If the fix needs to BOOST GREEN, the source was too
    magenta, so the corrective move is toward green => negative Tint (in Lumetri, negative
    Tint is green, positive is magenta).

    We measure these as log-ratios of the gains (log space is the natural home of
    multiplicative gains: it makes "twice as much blue" and "half as much blue" symmetric).
    """
    gr, gg, gb = gains
    temp = -K_TEMP * np.log(gb / gr)
    tint = -K_TINT * np.log(gg / np.sqrt(gr * gb))
    temp = float(np.clip(temp, -100.0, 100.0))
    tint = float(np.clip(tint, -100.0, 100.0))
    return temp, tint


def estimate_white_balance(img_linear: np.ndarray, patch_linear: np.ndarray | None = None) -> WBResult:
    """Top-level WB estimate. Pass a linear neutral patch for a precise result, else we
    fall back to a gray-world guess over the whole linear frame."""
    if patch_linear is not None:
        gains, note = gains_from_neutral_patch(patch_linear)
        method, confidence = "neutral-patch", "high"
        pm = patch_linear.reshape(-1, 3).mean(axis=0)
        patch_mean = (float(pm[0]), float(pm[1]), float(pm[2]))
    else:
        gains, note = gains_from_gray_world(img_linear)
        method, confidence = "gray-world", "low"
        patch_mean = None

    temp, tint = gains_to_lumetri(gains)
    return WBResult(
        gains=gains, method=method, confidence=confidence,
        lumetri_temp=temp, lumetri_tint=tint,
        patch_rgb_linear=patch_mean, note=note,
    )


def apply_gains_linear(img_linear: np.ndarray, gains) -> np.ndarray:
    """Apply per-channel gains to a linear RGB array (broadcasts over the last axis)."""
    return np.asarray(img_linear, dtype=np.float64) * np.asarray(gains, dtype=np.float64)
