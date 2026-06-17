"""gradekit — a local, offline color-analysis tool + .cube LUT baker.

Point it at a single video frame or image. It tells you what's wrong with the color
(in plain language AND in Premiere Lumetri terms), then bakes the corrective fix into a
.cube LUT you can drop into Lumetri -> Creative -> Look.

Design promises:
  * 100% local. The only subprocess ever launched is ffmpeg/ffprobe. No network, ever.
  * The color math is written by hand and commented with the *why* (see colorscience.py).
    numpy is used only as a fast array calculator, not as a color-science black box.
  * It never hard-fails on a missing optional dependency (cv2). Face detection degrades
    gracefully to a pure-numpy fallback.
"""

__version__ = "0.1.1"
