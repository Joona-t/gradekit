"""make_test_frame.py — synthesize a KNOWN-BAD frame with ground truth we can assert on.

We build a clean sRGB image (neutral gray patch, a skin chip at a known hue, pure
white/black blocks, a couple of color chips), then inject a KNOWN color cast and exposure
offset *in linear light*. Because we know exactly what we did to it, the tests can check
that gradekit recovers it: the WB gains should invert the cast, the corrected neutral
patch should read neutral, the white/black blocks should register as clipped, etc.

Run standalone to drop a frame on disk:
    python3 tests/make_test_frame.py /tmp/gradekit_test.png
"""
import os
import sys

# Make this runnable both under pytest and as a standalone script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np  # noqa: E402

from gradekit import colorscience as cs  # noqa: E402
from gradekit import frameio  # noqa: E402

# The cast/exposure we INJECT (and therefore expect gradekit to recover the inverse of).
CAST_GAINS = (1.30, 1.00, 0.70)   # warm: more red, less blue (applied in linear light)
EXPOSURE_FACTOR = 0.85            # slightly underexposed (uniform linear scale)


def make(path: str, size_hw=(240, 360)) -> dict:
    H, W = size_hw
    enc = np.full((H, W, 3), 0.45, dtype=np.float64)  # mid-gray background

    def put(region, rgb):
        x, y, w, h = region
        enc[y:y + h, x:x + w] = rgb

    neutral = (20, 20, 60, 60)
    skin = (120, 20, 60, 60)
    white = (220, 20, 60, 60)
    black = (20, 120, 60, 60)
    put(neutral, (0.60, 0.60, 0.60))    # should read neutral; cast will tilt it
    put(skin, (0.85, 0.62, 0.48))       # healthy skin chip (hue ~23 deg)
    put(white, (1.0, 1.0, 1.0))         # pure white -> will clip after the warm cast
    put(black, (0.0, 0.0, 0.0))         # pure black -> crushed
    put((120, 120, 60, 60), (0.20, 0.45, 0.75))   # blue-ish chip (realism)
    put((220, 120, 60, 60), (0.60, 0.25, 0.30))   # dull-red chip (realism)

    # Inject the cast + exposure in LINEAR light, then re-encode and quantize to 8-bit.
    lin = cs.srgb_to_linear(enc)
    lin = lin * np.array(CAST_GAINS, dtype=np.float64) * EXPOSURE_FACTOR
    out_enc = np.clip(cs.linear_to_srgb(np.clip(lin, 0.0, None)), 0.0, 1.0)
    frameio.save_image_rgb(path, out_enc)

    return {
        "neutral": neutral, "skin": skin, "white": white, "black": black,
        "cast_gains": CAST_GAINS, "exposure_factor": EXPOSURE_FACTOR, "size": (H, W),
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "gradekit_test.png"
    info = make(out)
    print(f"wrote {out}")
    print(f"  neutral patch: {info['neutral']}   skin chip: {info['skin']}")
    print(f"  injected cast gains {info['cast_gains']}, exposure x{info['exposure_factor']}")
