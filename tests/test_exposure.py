import make_test_frame as mtf
from gradekit import colorscience as cs
from gradekit import exposure as ex
from gradekit import frameio


def _exposure(tmp_path):
    path = tmp_path / "frame.png"
    mtf.make(str(path))
    lin = cs.srgb_to_linear(frameio.load_image_rgb(str(path)))
    return ex.analyze_exposure(lin)


def test_clipping_detected(tmp_path):
    r = _exposure(tmp_path)
    assert r.blown_pct > 1.0     # the pure-white block clips after the warm cast
    assert r.crushed_pct > 1.0   # the pure-black block


def test_underexposure_detected(tmp_path):
    r = _exposure(tmp_path)
    # We injected a 0.85x exposure (darker), so the tool should recommend +exposure.
    assert r.exposure_stops > 0.0
    assert r.rec_exposure > 0.0
