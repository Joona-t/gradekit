import numpy as np

import make_test_frame as mtf
from gradekit import colorscience as cs
from gradekit import frameio
from gradekit import whitebalance as wb


def _load(tmp_path):
    path = tmp_path / "frame.png"
    info = mtf.make(str(path))
    arr = frameio.load_image_rgb(str(path))
    return arr, info


def test_neutral_patch_inverts_injected_cast(tmp_path):
    arr, info = _load(tmp_path)
    lin = cs.srgb_to_linear(arr)
    patch_lin = cs.srgb_to_linear(frameio.crop_region(arr, info["neutral"]))
    res = wb.estimate_white_balance(lin, patch_linear=patch_lin)

    gr, gg, gb = res.gains
    cr, cg, cb = info["cast_gains"]
    # Recovered gain ratios should be the inverse of the injected cast ratios.
    assert abs((gr / gg) - (cg / cr)) < 0.12
    assert abs((gb / gg) - (cg / cb)) < 0.12
    # A warm source should be corrected with a COOLER move => negative Temperature.
    assert res.lumetri_temp < 0
    assert res.confidence == "high"


def test_corrected_neutral_patch_reads_neutral(tmp_path):
    arr, info = _load(tmp_path)
    lin = cs.srgb_to_linear(arr)
    patch_lin = cs.srgb_to_linear(frameio.crop_region(arr, info["neutral"]))
    res = wb.estimate_white_balance(lin, patch_linear=patch_lin)

    corrected = wb.apply_gains_linear(patch_lin, res.gains).reshape(-1, 3).mean(axis=0)
    spread = (corrected.max() - corrected.min()) / corrected.mean()
    assert spread < 0.06   # R, G, B within a few percent of each other => neutral


def test_gray_world_runs_and_clamps(tmp_path):
    arr, _ = _load(tmp_path)
    lin = cs.srgb_to_linear(arr)
    res = wb.estimate_white_balance(lin, patch_linear=None)
    assert res.method == "gray-world"
    assert res.confidence == "low"
    assert all(wb.GAIN_MIN <= g <= wb.GAIN_MAX for g in res.gains)


def test_gains_to_lumetri_signs():
    # Boosting blue / cutting red corrects a warm image -> negative Temperature.
    temp, _ = wb.gains_to_lumetri((0.8, 1.0, 1.25))
    assert temp < 0
    # Boosting red / cutting blue corrects a cool image -> positive Temperature.
    temp2, _ = wb.gains_to_lumetri((1.25, 1.0, 0.8))
    assert temp2 > 0
