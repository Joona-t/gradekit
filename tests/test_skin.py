import numpy as np

import make_test_frame as mtf
from gradekit import colorscience as cs
from gradekit import frameio
from gradekit import skin
from gradekit import whitebalance as wb


def _corrected_frame(tmp_path):
    """Return (corrected_encoded_frame, info) — WB applied, as the tool judges skin."""
    path = tmp_path / "frame.png"
    info = mtf.make(str(path))
    arr = frameio.load_image_rgb(str(path))
    lin = cs.srgb_to_linear(arr)
    patch_lin = cs.srgb_to_linear(frameio.crop_region(arr, info["neutral"]))
    res = wb.estimate_white_balance(lin, patch_linear=patch_lin)
    corrected_lin = wb.apply_gains_linear(lin, res.gains)
    corrected_enc = np.clip(cs.linear_to_srgb(np.clip(corrected_lin, 0.0, None)), 0.0, 1.0)
    return corrected_enc, info


def test_explicit_skin_region_reads_healthy(tmp_path):
    frame, info = _corrected_frame(tmp_path)
    res = skin.analyze_skin(frame, region=info["skin"])
    assert res is not None
    assert 12.0 <= res.hue <= 48.0   # near the 20-40 healthy band
    assert res.sat < 0.7


def test_ycbcr_separates_skin_from_gray(tmp_path):
    frame, info = _corrected_frame(tmp_path)
    mask = skin.skin_mask_ycbcr(frame)

    sx, sy, sw, sh = info["skin"]
    nx, ny, nw, nh = info["neutral"]
    skin_fraction = mask[sy:sy + sh, sx:sx + sw].mean()
    gray_fraction = mask[ny:ny + nh, nx:nx + nw].mean()

    assert skin_fraction > 0.5   # the skin chip should register as skin
    assert gray_fraction < 0.2   # the neutral gray chip should not
