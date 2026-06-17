"""exposure.py — read the tone of a frame from its luminance histogram and translate
that into Lumetri Basic-panel moves (Exposure, Highlights, Whites, Shadows, Blacks).

We deliberately measure in two different spaces:

  * CLIPPING is about code values hitting the ceiling or floor — "is this pixel pinned at
    255 or at 0?" — so we detect it on the ENCODED (display) signal. We check it PER
    CHANNEL (max channel at the ceiling = blown, min channel at the floor = crushed),
    because a single clipped channel already destroys detail and skews hue (a blown red in
    a warm highlight is exactly why over-warm skies go magenta).

  * EXPOSURE DIRECTION (how many stops to move) is a multiplicative operation on light, so
    the math only makes sense on LINEAR luminance. A "stop" is a factor of 2 in light, and
    factors live in linear space.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import colorscience as cs

# 18% mid-gray is the classic exposure anchor (a gray card reflects ~18% of light). In
# linear light that's ~0.18; we aim the frame's median luminance toward it.
TARGET_LINEAR_MEDIAN = 0.18

CLIP_HI = 0.99   # encoded luma at/above this counts as a blown highlight
CLIP_LO = 0.01   # encoded luma at/below this counts as a crushed black


@dataclass
class ExposureResult:
    blown_pct: float          # % of pixels with blown highlights
    crushed_pct: float        # % of pixels with crushed blacks
    p1: float                 # 1st percentile of encoded luma (the "floor" of real detail)
    p50: float                # median encoded luma
    p99: float                # 99th percentile (the "ceiling" of real detail)
    median_linear: float
    exposure_stops: float     # the exposure correction we will BAKE into the LUT
    rec_exposure: float       # Lumetri Exposure (stops)        [baked]
    rec_highlights: float     # Lumetri Highlights (-100..100)  [dial on top]
    rec_whites: float         # Lumetri Whites                  [dial on top]
    rec_shadows: float        # Lumetri Shadows                 [dial on top]
    rec_blacks: float         # Lumetri Blacks                  [dial on top]
    rec_contrast: float       # suggested Lumetri Contrast if flat [dial on top]
    flat: bool


def analyze_exposure(img_linear: np.ndarray) -> ExposureResult:
    rgb_enc = cs.linear_to_srgb(img_linear)  # per-channel display signal (round-trips source)
    luma_lin = cs.luminance_linear(img_linear)
    luma_enc = cs.linear_to_srgb(luma_lin)   # display-space luma for percentiles

    n_pix = luma_enc.size
    # Per-channel clip detection: any channel pinned at the ceiling/floor loses detail.
    maxc = rgb_enc.max(axis=-1)
    minc = rgb_enc.min(axis=-1)
    blown = float((maxc >= CLIP_HI).sum()) / n_pix * 100.0
    crushed = float((minc <= CLIP_LO).sum()) / n_pix * 100.0
    p1, p50, p99 = (float(x) for x in np.percentile(luma_enc, [1.0, 50.0, 99.0]))

    median_lin = float(np.median(luma_lin))
    # Exposure in stops = log2(target / current). Guard the log against a black frame.
    safe_median = max(median_lin, 1e-4)
    stops = float(np.clip(np.log2(TARGET_LINEAR_MEDIAN / safe_median), -3.0, 3.0))

    # --- Heuristic Lumetri recommendations. All are STARTING POINTS, clamped to sane ---
    # --- ranges. Severity-to-slider scaling is intentionally gentle and documented.   ---

    # Exposure: the Lumetri slider is literally in stops, so pass it through (1 decimal).
    rec_exposure = round(stops, 1)

    # Highlights/Whites pull blown detail back down; scale with how much is clipping.
    rec_highlights = -min(80.0, blown * 8.0) if blown > 1.0 else 0.0
    rec_whites = -min(60.0, blown * 5.0) if blown > 2.0 else 0.0

    # Shadows/Blacks lift crushed detail back up.
    rec_shadows = min(80.0, crushed * 8.0) if crushed > 1.0 else 0.0
    rec_blacks = min(60.0, crushed * 5.0) if crushed > 2.0 else 0.0

    # Flatness: a small spread between the 1st and 99th percentiles means low contrast.
    spread = p99 - p1
    flat = spread < 0.55
    rec_contrast = round(min(40.0, (0.55 - spread) * 120.0)) if flat else 0.0

    return ExposureResult(
        blown_pct=blown, crushed_pct=crushed,
        p1=p1, p50=p50, p99=p99,
        median_linear=median_lin, exposure_stops=stops,
        rec_exposure=rec_exposure,
        rec_highlights=round(rec_highlights), rec_whites=round(rec_whites),
        rec_shadows=round(rec_shadows), rec_blacks=round(rec_blacks),
        rec_contrast=float(rec_contrast), flat=flat,
    )
