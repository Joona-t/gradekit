"""colorscience.py — hand-written color math, commented with the *why*.

Nothing in here is a black box. Every transform is implemented straight from its
definition so you can read the science off the page. The only library is numpy, and it's
used purely as a fast elementwise calculator — it does no color science for us.

THE ONE IDEA THAT DRIVES THE WHOLE TOOL
---------------------------------------
An 8-bit image is *gamma-encoded* (it uses the sRGB transfer function). The numbers
stored in the file are NOT proportional to light energy — they're perceptually spaced so
that 8 bits look smooth to the eye. White balance and exposure, however, are *physical*
operations on light: they multiply photon counts. Multiplication is only meaningful in a
space where the numbers are proportional to light, i.e. LINEAR space.

So the correct order is always:  un-gamma -> do the math in linear -> re-gamma.

If you instead scale the raw sRGB numbers directly (which most quick tutorials do), you
bend the result: midtones shift the wrong way, color mixtures go muddy, and highlights
roll off oddly. That muddy look is the tell-tale sign of a grade done in the wrong space.
"""
from __future__ import annotations

import numpy as np

# Rec.709 / sRGB luminance weights (the middle row of the linear-sRGB -> XYZ matrix).
# These apply to LINEAR RGB, never to encoded sRGB. Green dominates because the human eye
# is far more sensitive to green light than to red or blue.
LUMA_R, LUMA_G, LUMA_B = 0.2126, 0.7152, 0.0722


def srgb_to_linear(v):
    """Decode gamma-encoded sRGB (0..1) -> linear light (0..1).

    The sRGB transfer function is a short linear "toe" near black spliced onto a power
    curve. The piecewise split at 0.04045 keeps the curve smooth and avoids the infinite
    slope at zero that a pure power curve would have (which would crush near-black noise).
    """
    v = np.asarray(v, dtype=np.float64)
    linear_segment = v / 12.92
    power_segment = ((v + 0.055) / 1.055) ** 2.4
    # np.where evaluates both branches then selects; that's fine here (both are defined
    # for the whole 0..1 range) and it keeps the code vectorized.
    return np.where(v <= 0.04045, linear_segment, power_segment)


def linear_to_srgb(L):
    """Encode linear light (0..1) -> gamma-encoded sRGB (0..1). Exact inverse of the above.

    We always do white-balance / exposure work in linear and then come back through here
    before writing pixels or building the (display-referred) .cube LUT.
    """
    L = np.asarray(L, dtype=np.float64)
    # Clip negatives before the fractional power so we never take a root of a negative.
    L_clipped = np.clip(L, 0.0, None)
    linear_segment = 12.92 * L
    power_segment = 1.055 * np.power(L_clipped, 1.0 / 2.4) - 0.055
    return np.where(L <= 0.0031308, linear_segment, power_segment)


def luminance_linear(rgb_linear):
    """Rec.709 relative luminance from LINEAR RGB. Input shape (..., 3) -> output (...)."""
    rgb_linear = np.asarray(rgb_linear, dtype=np.float64)
    r = rgb_linear[..., 0]
    g = rgb_linear[..., 1]
    b = rgb_linear[..., 2]
    return LUMA_R * r + LUMA_G * g + LUMA_B * b


def rgb_to_hsv(rgb):
    """RGB (0..1) -> HSV with Hue in DEGREES (0..360), Sat/Val in 0..1.

    This is the standard hexagonal-model conversion, written out by hand. We use HSV for
    skin analysis because "skin hue ~20-40 degrees" is the language colorists actually
    speak, and hue/saturation map cleanly onto "too warm" / "oversaturated" judgements.

    Feed it ENCODED sRGB (not linear) so the reported hue matches what your eye sees on a
    monitor — hue in encoded space is what tools like Lumetri's HSL panel operate on.
    """
    rgb = np.asarray(rgb, dtype=np.float64)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    cmax = np.maximum(np.maximum(r, g), b)   # the dominant channel sets Value
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin                       # chroma: 0 means gray (no hue)

    # Avoid divide-by-zero on achromatic pixels by substituting 1.0 in the denominator
    # wherever delta is ~0; we mask those hues back to 0 afterwards.
    nonzero = delta > 1e-12
    safe_delta = np.where(nonzero, delta, 1.0)

    # Each channel's "distance" used to place the hue inside its 60-degree sector.
    rc = (g - b) / safe_delta
    gc = (b - r) / safe_delta + 2.0
    bc = (r - g) / safe_delta + 4.0

    # Pick the sector based on which channel is the maximum.
    hue = np.where(cmax == r, rc, np.where(cmax == g, gc, bc))
    hue = (hue * 60.0) % 360.0
    hue = np.where(nonzero, hue, 0.0)

    sat = np.where(cmax > 1e-12, delta / np.where(cmax > 1e-12, cmax, 1.0), 0.0)
    val = cmax

    return np.stack([hue, sat, val], axis=-1)


def hsv_to_rgb(hsv):
    """HSV (H degrees, S/V 0..1) -> RGB 0..1. Inverse of rgb_to_hsv (used in round-trip tests)."""
    hsv = np.asarray(hsv, dtype=np.float64)
    h = (hsv[..., 0] % 360.0) / 60.0   # which of the 6 sectors, plus fractional position
    s = hsv[..., 1]
    v = hsv[..., 2]

    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    # For each of the 6 hue sectors, R/G/B take a different one of {v, q, p, t}.
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)
