import numpy as np

from gradekit import lut


def test_identity_lut_is_identity():
    # No correction -> the LUT must be a near-perfect identity.
    size = 17
    cube = lut.build_lut(size, (1.0, 1.0, 1.0), 0.0, 0.0)
    rng = np.random.default_rng(1)
    img = rng.random((40, 40, 3))
    out = lut.apply_lut_trilinear(img, cube, size)
    assert np.allclose(out, img, atol=1e-6)


def test_cube_format_valid(tmp_path):
    size = 33
    cube = lut.build_lut(size, (0.8, 1.0, 1.3), 0.2, 0.1)
    path = tmp_path / "look.cube"
    n = lut.write_cube(str(path), cube, size)
    assert n == size ** 3

    ok, size_seen, rows_seen, problems = lut.validate_cube(str(path))
    assert ok, problems
    assert size_seen == 33
    assert rows_seen == 33 ** 3


def test_cube_has_expected_header(tmp_path):
    size = 5
    cube = lut.build_lut(size, (1.0, 1.0, 1.0), 0.0, 0.0)
    path = tmp_path / "h.cube"
    lut.write_cube(str(path), cube, size)
    text = path.read_text()
    assert "LUT_3D_SIZE 5" in text
    assert "DOMAIN_MIN 0.0 0.0 0.0" in text
    assert "DOMAIN_MAX 1.0 1.0 1.0" in text


def test_trilinear_matches_direct_pipeline():
    # The LUT (sampled + trilinearly interpolated) should match running the pipeline
    # directly on every pixel, within small interpolation error.
    size = 33
    gains, exp, con = (0.8, 1.0, 1.3), 0.1, 0.1
    cube = lut.build_lut(size, gains, exp, con)
    rng = np.random.default_rng(2)
    img = rng.random((64, 64, 3))
    direct = lut.apply_pipeline_encoded(img, gains, exp, con)
    via_lut = lut.apply_lut_trilinear(img, cube, size)
    assert np.allclose(direct, via_lut, atol=0.02)


def test_contrast_zero_is_identity():
    x = np.linspace(0, 1, 50)
    assert np.allclose(lut.contrast_scurve(x, 0.0), x)


def test_contrast_fixes_endpoints_and_midpoint():
    x = np.array([0.0, 0.5, 1.0])
    y = lut.contrast_scurve(x, 0.5)
    assert np.allclose(y, [0.0, 0.5, 1.0], atol=1e-9)
