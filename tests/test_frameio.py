import numpy as np

from gradekit import frameio


def test_luma99_orders_by_brightness():
    """The brightest-frame picker ranks frames by _luma99; a brighter frame must score higher
    so extract_brightest_frame selects the worst-case (most-likely-to-clip) frame."""
    dim = np.full((16, 16, 3), 0.30)
    bright = np.full((16, 16, 3), 0.95)
    assert frameio._luma99(bright) > frameio._luma99(dim)


def test_luma99_ignores_tiny_speckle():
    """99.5th percentile ignores a handful of stray hot pixels, so a single specular glint
    doesn't make an otherwise-normal frame masquerade as the brightest."""
    frame = np.full((100, 100, 3), 0.40)
    frame[0, 0] = 1.0  # one blown pixel (0.01% of the frame)
    assert frameio._luma99(frame) < 0.5
