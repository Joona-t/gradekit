"""report.py — turn the analysis into a clean, scannable terminal report.

Format per issue: one WHAT'S WRONG line, one WHY line, then the exact Lumetri values.
We clearly separate values that are already [baked] into the .cube from values you should
[dial] by hand on top of it, so you never accidentally double-apply a correction.
"""
from __future__ import annotations

import sys


# ---- tiny ANSI helper (auto-disables when output isn't a terminal) -------------------
_USE_COLOR = sys.stdout.isatty()
_CODES = {"red": "31", "green": "32", "yellow": "33", "blue": "34",
          "dim": "2", "bold": "1"}


def _c(text, *styles):
    if not _USE_COLOR or not styles:
        return text
    seq = ";".join(_CODES[s] for s in styles if s in _CODES)
    return f"\033[{seq}m{text}\033[0m"


def _bad(s):
    return _c("✗ " + s, "red")        # ✗


def _warn(s):
    return _c("⚠ " + s, "yellow")     # ⚠


def _ok(s):
    return _c("✓ " + s, "green")      # ✓


def _why(s):
    return "    " + _c("why: " + s, "dim")


def _dial(label, s):
    return "    " + _c(label, "dim") + "  " + s


def _fmt_signed(v, decimals=0):
    """Format a Lumetri value with an explicit + / - sign (e.g. '+12', '-0.4')."""
    if decimals:
        return f"{v:+.{decimals}f}"
    return f"{int(round(v)):+d}"


def _section(title, tag=""):
    head = _c(title, "bold")
    if tag:
        head += "  " + _c(f"[{tag}]", "dim")
    return "\n" + head


def build_report(ctx) -> str:
    """ctx is a dict assembled by cli.cmd_analyze with keys:
       input, info, wb, exposure, skin, skin_skipped, lut_path, lut_size, lut_rows,
       lut_ok, preview_path, contrast."""
    wb = ctx["wb"]
    ex = ctx["exposure"]
    sk = ctx["skin"]
    L = []

    # ---- header ----
    info = ctx["info"]
    src = "image" if info["kind"] == "image" else f"video frame @ {info['t']:.2f}s"
    L.append(_c(f"gradekit  —  {ctx['input']}  ({src})", "bold"))
    L.append(_c("─" * 64, "dim"))
    L.append(
        "The .cube bakes: White Balance + Exposure + gentle Contrast.\n"
        "Drop it into Lumetri → Creative → Look. Values tagged "
        + _c("[baked]", "dim") + " are already in the\nLUT (shown so you can understand/tweak it); "
        + _c("[dial]", "dim") + " values are extra moves to add by hand."
    )

    # ---- white balance ----
    L.append(_section("WHITE BALANCE", f"method: {wb.method} · confidence: {wb.confidence}"))
    gr, gg, gb = wb.gains
    temp, tint = wb.lumetri_temp, wb.lumetri_tint
    cast_strong = abs(temp) > 8 or abs(tint) > 8
    if cast_strong:
        # Name the cast direction from the corrective Lumetri move.
        bits = []
        if temp < -8:
            bits.append("warm/amber")
        elif temp > 8:
            bits.append("cool/blue")
        if tint < -8:
            bits.append("magenta")
        elif tint > 8:
            bits.append("green")
        name = " + ".join(bits) if bits else "color"
        L.append("  " + _bad(f"{name.capitalize()} cast."))
        L.append(_why(f"sample reads unbalanced in linear light (gains "
                      f"{gr:.2f} / {gg:.2f} / {gb:.2f} for R/G/B)."))
        L.append(_dial("Lumetri → Basic [baked]:",
                       f"Temperature {_fmt_signed(temp)}   Tint {_fmt_signed(tint)}"))
        if wb.confidence == "low":
            L.append("    " + _c("(gray-world guess — pass --neutral x,y,w,h for a precise result)", "dim"))
    else:
        L.append("  " + _ok("White balance looks neutral."))
        if wb.confidence == "low":
            L.append("    " + _c("(gray-world guess; --neutral would confirm)", "dim"))

    # ---- exposure ----
    L.append(_section("EXPOSURE"))
    any_exposure_issue = False
    if abs(ex.exposure_stops) >= 0.25:
        any_exposure_issue = True
        if ex.exposure_stops > 0:
            L.append("  " + _bad("Underexposed — midtones sit below mid-gray."))
            L.append(_why(f"median luma is about {ex.exposure_stops:+.1f} stops under the 18% target."))
        else:
            L.append("  " + _bad("Overexposed — midtones sit above mid-gray."))
            L.append(_why(f"median luma is about {ex.exposure_stops:+.1f} stops over the 18% target."))
        L.append(_dial("Lumetri → Basic [baked]:", f"Exposure {_fmt_signed(ex.rec_exposure, 1)}"))

    if ex.blown_pct > 1.0 or ex.crushed_pct > 1.0:
        any_exposure_issue = True
        L.append("  " + _bad(f"{ex.blown_pct:.1f}% highlights blown · {ex.crushed_pct:.1f}% shadows crushed."))
        L.append(_why("pixels pinned at the ceiling/floor carry no recoverable detail."))
        moves = []
        if ex.rec_highlights:
            moves.append(f"Highlights {_fmt_signed(ex.rec_highlights)}")
        if ex.rec_whites:
            moves.append(f"Whites {_fmt_signed(ex.rec_whites)}")
        if ex.rec_shadows:
            moves.append(f"Shadows {_fmt_signed(ex.rec_shadows)}")
        if ex.rec_blacks:
            moves.append(f"Blacks {_fmt_signed(ex.rec_blacks)}")
        if moves:
            L.append(_dial("Lumetri → Basic [dial]: ", "   ".join(moves)))

    if ex.flat:
        any_exposure_issue = True
        L.append("  " + _warn("Image looks flat (low contrast)."))
        L.append(_why(f"the 1–99 percentile spread is only {ex.p99 - ex.p1:.2f} of the range."))
        L.append(_dial("Lumetri → Basic [dial]: ", f"Contrast {_fmt_signed(ex.rec_contrast)} "
                       + _c("(or rely on the LUT's baked contrast)", "dim")))
    if not any_exposure_issue:
        L.append("  " + _ok("Exposure and contrast look fine."))

    # ---- skin ----
    if ctx.get("skin_skipped"):
        L.append(_section("SKIN"))
        L.append("  " + _c("— no region given and no face/skin detected; skipped. "
                           "Pass --skin x,y,w,h to analyze skin.", "dim"))
    elif sk is not None:
        L.append(_section("SKIN", f"sample: {sk.method} · judged post-WB"))
        if sk.healthy:
            L.append("  " + _ok(f"Skin hue {sk.hue:.0f}° (target 20–40), "
                                f"saturation {sk.sat * 100:.0f}% — healthy."))
        else:
            for flag in sk.flags:
                L.append("  " + _warn(flag))
            L.append(_why(f"measured hue {sk.hue:.0f}°, saturation {sk.sat * 100:.0f}%."))
            L.append("    " + _c("(your call — not baked. Try Lumetri → HSL Secondary "
                                "to nudge hue toward ~30°.)", "dim"))

    # ---- outputs ----
    L.append(_section("LUT"))
    if ctx["lut_ok"]:
        L.append("  " + _ok(f"wrote {ctx['lut_path']}  "
                            f"({ctx['lut_size']}×{ctx['lut_size']}×{ctx['lut_size']}, "
                            f"{ctx['lut_rows']} rows, format valid)"))
    else:
        L.append("  " + _bad(f"LUT validation FAILED for {ctx['lut_path']}: {ctx.get('lut_problems')}"))
    if ctx.get("preview_path"):
        L.append(_section("PREVIEW"))
        L.append("  " + _ok(f"wrote {ctx['preview_path']}  (before | after, after = baked LUT applied)"))

    return "\n".join(L) + "\n"


def print_report(ctx) -> None:
    print(build_report(ctx))
