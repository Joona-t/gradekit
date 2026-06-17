import numpy as np

from gradekit import colorscience as cs


def test_srgb_to_linear_roundtrip():
    v = np.linspace(0.0, 1.0, 257)
    assert np.allclose(cs.linear_to_srgb(cs.srgb_to_linear(v)), v, atol=1e-9)


def test_linear_to_srgb_roundtrip():
    L = np.linspace(0.0, 1.0, 257)
    assert np.allclose(cs.srgb_to_linear(cs.linear_to_srgb(L)), L, atol=1e-9)


def test_known_srgb_points():
    # sRGB(1.0) == linear 1.0; sRGB ~0.5 -> linear ~0.214 (the classic mid-gray fact).
    assert abs(float(cs.srgb_to_linear(np.array(1.0))) - 1.0) < 1e-9
    assert abs(float(cs.srgb_to_linear(np.array(0.0))) - 0.0) < 1e-9
    assert abs(float(cs.srgb_to_linear(np.array(0.5))) - 0.2140) < 1e-3


def test_hsv_roundtrip():
    rng = np.random.default_rng(0)
    rgb = rng.random((2000, 3))
    back = cs.hsv_to_rgb(cs.rgb_to_hsv(rgb))
    assert np.allclose(back, rgb, atol=1e-6)


def test_gray_has_zero_saturation():
    hsv = cs.rgb_to_hsv(np.array([[0.5, 0.5, 0.5]]))[0]
    assert hsv[1] < 1e-9


def test_pure_red_hue_is_zero():
    hsv = cs.rgb_to_hsv(np.array([[1.0, 0.0, 0.0]]))[0]
    assert hsv[0] < 1e-6 or abs(hsv[0] - 360.0) < 1e-6
    assert abs(hsv[1] - 1.0) < 1e-9
