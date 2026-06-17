"""cli.py — argument parsing and orchestration for `gradekit analyze`.

Flow:
  load frame -> linearize -> white balance -> exposure -> skin -> bake .cube -> validate
  -> optional before/after preview -> print report.

Everything is local; the only subprocess is ffmpeg/ffprobe inside frameio.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from . import __version__
from . import colorscience as cs
from . import exposure as exposure_mod
from . import frameio
from . import lut as lut_mod
from . import report as report_mod
from . import skin as skin_mod
from . import whitebalance as wb_mod


def parse_region(s: str):
    """Parse a 'x,y,w,h' string into an (int, int, int, int) tuple."""
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("expected four comma-separated numbers: x,y,w,h")
    try:
        x, y, w, h = (int(round(float(p))) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("region values must be numbers: x,y,w,h")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("width and height must be positive")
    return (x, y, w, h)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gradekit",
        description="Local color-analysis tool: diagnose a frame and bake the fix into a .cube LUT.",
    )
    p.add_argument("--version", action="version", version=f"gradekit {__version__}")
    sub = p.add_subparsers(dest="command")

    a = sub.add_parser("analyze", help="analyze a video/image and write a corrective .cube LUT")
    a.add_argument("input", help="path to a video or image")
    a.add_argument("--t", type=float, default=None,
                   help="grab the frame at this timestamp in seconds (video only; default ~10%% in)")
    a.add_argument("--neutral", type=parse_region, default=None,
                   help="region 'x,y,w,h' that should read neutral white/gray (drives precise WB)")
    a.add_argument("--skin", type=parse_region, default=None,
                   help="optional skin sample region 'x,y,w,h'")
    a.add_argument("--lut", default=None,
                   help="output .cube path (default: ./<input-stem>.cube)")
    a.add_argument("--size", type=int, default=33, help="LUT cube size (default 33, min 2)")
    a.add_argument("--preview", default=None, help="write a before/after PNG to this path")
    a.add_argument("--contrast", type=float, default=0.10,
                   help="gentle contrast S-curve strength baked into the LUT (default 0.10; 0 = none)")
    return p


def cmd_analyze(args) -> int:
    if args.size < 2:
        print("error: --size must be >= 2", file=sys.stderr)
        return 2

    # 1) Load a single frame as encoded RGB in [0,1].
    arr_encoded, info = frameio.load_frame(args.input, t=args.t)
    img_linear = cs.srgb_to_linear(arr_encoded)

    # 2) White balance — neutral patch if given, else gray-world.
    patch_linear = None
    if args.neutral is not None:
        patch_linear = cs.srgb_to_linear(frameio.crop_region(arr_encoded, args.neutral))
    wb = wb_mod.estimate_white_balance(img_linear, patch_linear=patch_linear)

    # 3) Exposure/tone — measured on the ORIGINAL frame (that's what's "wrong" with it).
    ex = exposure_mod.analyze_exposure(img_linear)

    # 4) Skin — judged on the WB-corrected frame (the graded skin, not the raw cast).
    corrected_linear = wb_mod.apply_gains_linear(img_linear, wb.gains)
    corrected_encoded = np.clip(cs.linear_to_srgb(np.clip(corrected_linear, 0.0, None)), 0.0, 1.0)
    skin_result = None
    skin_skipped = False
    if args.skin is not None:
        skin_result = skin_mod.analyze_skin(corrected_encoded, region=args.skin)
    else:
        skin_result = skin_mod.analyze_skin(corrected_encoded, region=None)
        if skin_result is None:
            skin_skipped = True

    # 5) Bake the LUT (WB + exposure + gentle contrast) and validate it.
    lut_path = args.lut or f"{os.path.splitext(os.path.basename(args.input))[0]}.cube"
    lut_bgr = lut_mod.build_lut(args.size, wb.gains, ex.exposure_stops, args.contrast)
    n_rows = lut_mod.write_cube(lut_path, lut_bgr, args.size, title="gradekit look")
    ok, size_seen, rows_seen, problems = lut_mod.validate_cube(lut_path)

    # 6) Optional before/after preview, rendered by applying the ACTUAL baked LUT.
    preview_path = None
    if args.preview is not None:
        after = lut_mod.apply_lut_trilinear(arr_encoded, lut_bgr, args.size)
        frameio.save_side_by_side(args.preview, arr_encoded, after)
        preview_path = args.preview

    # 7) Report.
    ctx = {
        "input": args.input, "info": info, "wb": wb, "exposure": ex,
        "skin": skin_result, "skin_skipped": skin_skipped,
        "lut_path": lut_path, "lut_size": args.size, "lut_rows": rows_seen,
        "lut_ok": ok, "lut_problems": problems,
        "preview_path": preview_path, "contrast": args.contrast,
    }
    report_mod.print_report(ctx)
    return 0 if ok else 1


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "analyze":
        parser.print_help()
        return 1
    try:
        return cmd_analyze(args)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        # Friendly one-line errors instead of a traceback for the common failure modes.
        print(f"gradekit: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
