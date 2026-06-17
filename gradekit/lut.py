"""lut.py — bake the correction into a .cube 3D LUT, validate it, and apply it.

A .cube LUT is just a 3D lookup table: feed it an (R, G, B) and it returns the graded
(R, G, B). We build it by running EVERY lattice point through the exact same pipeline we'd
apply to the image, so the LUT *is* the grade. Premiere reads .cube in Lumetri ->
Creative -> Look (and in the dedicated LUT slots).

Pipeline baked at each lattice point (the ORDER matters and is the whole point):
    encoded input
      -> linearize                 (un-gamma; now we're in light)
      -> per-channel WB gains       (linear, multiplicative)
      -> exposure gain x 2^stops    (linear, multiplicative)
      -> re-encode to sRGB          (back to display)
      -> gentle contrast S-curve    (in encoded space — see below)
      -> clamp to [0,1]

Why contrast in ENCODED space: perceptual contrast (and Lumetri's Contrast slider) acts
on the display signal, pivoting around mid-gray. Doing it in linear would crush shadows
and blow highlights unevenly. So WB+exposure go in linear; contrast goes in encoded.
"""
from __future__ import annotations

import numpy as np

from . import colorscience as cs


def contrast_scurve(x, amount: float):
    """Gentle S-curve around 0.5 in ENCODED space. amount in ~[0, 1]; 0 == identity.

    Built from a logistic (sigmoid) and then renormalized so the curve still passes
    exactly through (0,0), (0.5,0.5) and (1,1) — i.e. it steepens the midtones without
    moving black, white, or mid-gray. Small `amount` => barely-there contrast.
    """
    if amount <= 0.0:
        return np.asarray(x, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    a = amount * 6.0   # map amount 0..1 to a gentle..strong steepness

    def sig(t):
        return 1.0 / (1.0 + np.exp(-a * (t - 0.5)))

    lo, hi = sig(0.0), sig(1.0)            # endpoints of the raw sigmoid
    return (sig(x) - lo) / (hi - lo)        # renormalize so 0->0 and 1->1


def apply_pipeline_encoded(rgb_encoded, gains, exposure_stops: float, contrast: float):
    """Run the full grade on ENCODED RGB (any shape ending in 3). This is the single source
    of truth for the grade — both the LUT bake and the verification test call it."""
    rgb_encoded = np.asarray(rgb_encoded, dtype=np.float64)
    lin = cs.srgb_to_linear(rgb_encoded)
    lin = lin * np.asarray(gains, dtype=np.float64)     # white balance (linear)
    lin = lin * (2.0 ** float(exposure_stops))          # exposure (linear)
    enc = cs.linear_to_srgb(np.clip(lin, 0.0, None))    # back to display
    enc = contrast_scurve(enc, contrast)                # gentle contrast (encoded)
    return np.clip(enc, 0.0, 1.0)


def build_lut(size: int, gains, exposure_stops: float, contrast: float) -> np.ndarray:
    """Build the baked LUT as an array of shape (size, size, size, 3), indexed [b, g, r].

    The lattice samples each axis at `size` evenly spaced points from 0 to 1. We index it
    [blue, green, red] on purpose: when this is flattened in C-order for the .cube file,
    RED ends up varying fastest, which is exactly the .cube ordering convention.
    """
    if size < 2:
        raise ValueError("LUT size must be >= 2")
    axis = np.linspace(0.0, 1.0, size)
    # indexing="ij" => first output varies along axis 0, etc. We assign axis 0 to blue
    # (outer/slowest) and axis 2 to red (inner/fastest).
    blue_g, green_g, red_g = np.meshgrid(axis, axis, axis, indexing="ij")
    grid_rgb = np.stack([red_g, green_g, blue_g], axis=-1)   # input encoded RGB at each node
    return apply_pipeline_encoded(grid_rgb, gains, exposure_stops, contrast)


def write_cube(path: str, lut_bgr: np.ndarray, size: int, title: str = "gradekit look") -> int:
    """Write a .cube file. `lut_bgr` is the (size,size,size,3) array from build_lut.
    Returns the number of data rows written (should equal size**3)."""
    rows = lut_bgr.reshape(-1, 3)   # C-order flatten => red fastest, matching .cube
    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    # 6 decimals is plenty of precision for an 8/10-bit display pipeline.
    lines.extend(f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in rows)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return rows.shape[0]


def validate_cube(path: str):
    """Parse a .cube and sanity-check it. Returns (ok, size, n_rows, problems[]).

    Checks: a LUT_3D_SIZE line exists; the data-row count equals size**3; every value is a
    finite float in [0,1]. This is the format check the build runs before declaring done.
    """
    problems = []
    size = None
    data_rows = 0
    bad_values = 0

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            upper = line.upper()
            if upper.startswith("LUT_3D_SIZE"):
                try:
                    size = int(line.split()[1])
                except (IndexError, ValueError):
                    problems.append("LUT_3D_SIZE line is malformed")
                continue
            if upper.startswith(("TITLE", "DOMAIN_MIN", "DOMAIN_MAX", "LUT_1D_SIZE")):
                continue
            # Anything else should be three floats.
            parts = line.split()
            if len(parts) != 3:
                problems.append(f"data line is not 3 numbers: {line!r}")
                continue
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                problems.append(f"non-numeric data line: {line!r}")
                continue
            data_rows += 1
            for v in vals:
                if not np.isfinite(v) or v < -1e-6 or v > 1.0 + 1e-6:
                    bad_values += 1

    if size is None:
        problems.append("missing LUT_3D_SIZE header")
    else:
        expected = size ** 3
        if data_rows != expected:
            problems.append(f"expected {expected} data rows for size {size}, found {data_rows}")
    if bad_values:
        problems.append(f"{bad_values} value(s) outside [0,1] or non-finite")

    return (len(problems) == 0, size, data_rows, problems)


def apply_lut_trilinear(img_encoded: np.ndarray, lut_bgr: np.ndarray, size: int) -> np.ndarray:
    """Apply a 3D LUT to an ENCODED RGB image via hand-written trilinear interpolation.

    This is exactly what Premiere does internally to apply the LUT, so using it for the
    preview makes the "after" image an honest preview of what you'll get in Lumetri. It's
    also how the test proves the baked LUT matches the direct pipeline.

    Trilinear = linear interpolation in all three color axes: locate the cube cell the
    input falls in, then blend its 8 corner outputs by the fractional position.
    """
    lut = np.asarray(lut_bgr, dtype=np.float64).reshape(size, size, size, 3)  # [b, g, r, :]

    coords = np.clip(img_encoded, 0.0, 1.0) * (size - 1)
    r, g, b = coords[..., 0], coords[..., 1], coords[..., 2]

    r0 = np.floor(r).astype(int); g0 = np.floor(g).astype(int); b0 = np.floor(b).astype(int)
    r1 = np.minimum(r0 + 1, size - 1)
    g1 = np.minimum(g0 + 1, size - 1)
    b1 = np.minimum(b0 + 1, size - 1)
    fr = (r - r0)[..., None]   # fractional position within the cell, per axis
    fg = (g - g0)[..., None]
    fb = (b - b0)[..., None]

    # Eight corners of the enclosing cube cell (remember the LUT is indexed [b, g, r]).
    c000 = lut[b0, g0, r0]; c100 = lut[b0, g0, r1]
    c010 = lut[b0, g1, r0]; c110 = lut[b0, g1, r1]
    c001 = lut[b1, g0, r0]; c101 = lut[b1, g0, r1]
    c011 = lut[b1, g1, r0]; c111 = lut[b1, g1, r1]

    # Interpolate along red, then green, then blue.
    c00 = c000 * (1 - fr) + c100 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c11 = c011 * (1 - fr) + c111 * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    out = c0 * (1 - fb) + c1 * fb
    return np.clip(out, 0.0, 1.0)
