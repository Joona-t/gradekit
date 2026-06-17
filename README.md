# gradekit

A tiny, **100% local** command-line tool that looks at one video frame (or image), tells
you what's wrong with the color **in plain language and in Premiere Lumetri terms**, and
bakes the corrective fix into a `.cube` LUT you can drop straight into **Lumetri →
Creative → Look**.

It's also meant to be read. The color math is written out by hand and commented with the
*why* — see [`gradekit/colorscience.py`](gradekit/colorscience.py). numpy is used only as a
fast calculator, never as a color-science black box.

> **New here? Open [`How it works.html`](How%20it%20works.html)** — a single self-contained page
> that walks through the color science, the CLI, how to apply the `.cube` in *any* editor
> (Premiere / DaVinci Resolve / Final Cut / After Effects / OBS / ffmpeg), and how to drive
> gradekit from your AI agents.

```
gradekit  —  shot.mp4  (video frame @ 1.40s)
────────────────────────────────────────────────────────────────
The .cube bakes: White Balance + Exposure + gentle Contrast.

WHITE BALANCE  [method: neutral-patch · confidence: high]
  ✗ Warm/amber cast.
    why: sample reads unbalanced in linear light (gains 0.80 / 1.04 / 1.49 for R/G/B).
    Lumetri → Basic [baked]:  Temperature -62   Tint +3

EXPOSURE
  ✗ Underexposed — midtones sit below mid-gray.
    why: median luma is about +0.3 stops under the 18% target.
    Lumetri → Basic [baked]:  Exposure +0.3
  ✗ 4.2% highlights blown · 4.2% shadows crushed.
    why: pixels pinned at the ceiling/floor carry no recoverable detail.
    Lumetri → Basic [dial]:   Highlights -34   Whites -21   Shadows +34   Blacks +21

SKIN  [sample: explicit --skin · judged post-WB]
  ✓ Skin hue 23° (target 20–40), saturation 43% — healthy.

LUT
  ✓ wrote shot.cube  (33×33×33, 35937 rows, format valid)
```

---

## Companion: `premiere-grade-bot` (Claude Code skill)

gradekit tells you the fix and bakes the LUT; **premiere-grade-bot** *applies* it in Adobe
Premiere Pro for you, hands-free, via screen automation. It's a Claude Code skill (uses the
computer-use tools) that:

- creates an **adjustment layer** spanning the whole sequence,
- types gradekit's measured **Temperature / Tint / Exposure / Contrast** straight into Lumetri
  Basic (no slider dragging) — **or** loads the baked `.cube` via Creative → Look,
- verifies every step with a screenshot, and aborts rather than clicking blind.

Skill: [`skills/premiere-grade-bot/SKILL.md`](skills/premiere-grade-bot/SKILL.md). Install by
copying that folder into `~/.claude/skills/`. It's the least-brittle GUI path (menu- and
keyboard-driven); the zero-automation alternative is simply dragging gradekit's `.cube` into
Lumetri → Creative → Look yourself.

---

## Requirements

- **Python 3.11+**
- **numpy**, **Pillow**
- **ffmpeg / ffprobe** on your `PATH` (only used for *video* inputs; images don't need it)
- **OpenCV is optional** — it only upgrades automatic face detection. Without it, gradekit
  falls back to a pure-numpy skin detector, so it never fails on a missing dependency.

On macOS with Homebrew, `ffmpeg`, `numpy`, and `Pillow` are typically already present.

## Install / run (three ways)

**Zero install — straight from the repo:**
```bash
python3 -m gradekit analyze shot.mp4            # from inside the gradekit/ folder
# or, from anywhere:
/path/to/gradekit/bin/gradekit analyze shot.mp4
```

**Bare `gradekit` command via a symlink (no packaging):**
```bash
ln -s "$PWD/bin/gradekit" /opt/homebrew/bin/gradekit
gradekit analyze shot.mp4
```

**Bare `gradekit` command via pipx (clean, isolated):**
```bash
pipx install .
# (to also upgrade face detection: pipx install '.[face]')
```

## Usage

```
gradekit analyze <input>                       # video or image
  --t 5.0                  # grab the frame at 5.0s (video only; default ~10% in)
  --neutral x,y,w,h        # a region you KNOW should read neutral white/gray
  --skin x,y,w,h           # optional skin sample region
  --lut out.cube           # output LUT path (default: ./<input-stem>.cube)
  --size 33                # LUT cube size (default 33, min 2)
  --preview before_after.png
  --contrast 0.10          # gentle contrast strength baked into the LUT (0 = none)
```

### Finding `x,y,w,h`

Coordinates are pixels from the **top-left** of the frame: `x,y` is the corner, `w,h` the
size. A gray card or a white wall makes the best `--neutral` patch. Pick a flat,
mid-tone area — avoid specular highlights and anything colored.

### Examples

```bash
# Image, with a known-neutral gray card patch, write a LUT + preview:
gradekit analyze frame.png --neutral 820,500,80,80 --lut look.cube --preview ba.png

# Video, frame at 12s, sample skin on the cheek too:
gradekit analyze take2.mov --t 12 --neutral 100,100,60,60 --skin 640,360,50,50

# No neutral patch? It falls back to a gray-world auto-WB guess (lower confidence):
gradekit analyze clip.mp4
```

---

## How the [baked] vs [dial] split works

The `.cube` already contains **White Balance + Exposure + a gentle Contrast curve**. When
you load it in Lumetri → Creative → Look, those are applied for you.

- Numbers tagged **[baked]** (Temperature, Tint, Exposure) are shown so you can *understand
  or hand-tweak* the look — **don't also dial them**, or you'll double-apply.
- Numbers tagged **[dial]** (Highlights, Whites, Shadows, Blacks, Contrast) are **extra
  region moves not in the LUT** — add them by hand on top if you want them.

Skin is **diagnostic only** and never baked — hue/saturation choices for skin are yours.

---

## The science (the short version)

### 1. Work in linear light, not in sRGB
8-bit pixels are **gamma-encoded**: the numbers are perceptually spaced, not proportional
to light. White balance and exposure are *multiplications of light*, so they only make
sense in **linear** space. gradekit always does: **un-gamma → math → re-gamma**. Doing the
math directly on sRGB numbers is the single most common mistake and the reason amateur
grades look muddy. (`srgb_to_linear` / `linear_to_srgb`.)

### 2. White balance = per-channel gains (von Kries)
A neutral surface should have R = G = B in linear light. From a patch you mark with
`--neutral`, we compute a gain per channel that makes it neutral, using the patch's
**luminance** as the target so brightness doesn't change. With no patch, we fall back to
**gray-world** (assume the whole scene averages to gray). (`whitebalance.py`.)

### 3. Gains → approximate Lumetri Temperature/Tint
Lumetri's Temp/Tint scale is proprietary, so this is an explicit, calibrated
**approximation**: Temperature comes from how much blue-vs-red correction is needed
(boost blue ⇒ source was warm ⇒ cooler = negative Temp); Tint from green-vs-magenta.
Treat the numbers as a strong starting point, not exact Kelvin.

### 4. Exposure/tone from the histogram
Clipping is detected **per channel** in display space (any channel pinned at the
ceiling/floor loses detail). Exposure direction is computed in **linear** as
`log2(target / median)` toward an 18% mid-gray anchor. (`exposure.py`.)

### 5. The LUT
We sample a 33³ lattice of input colors and run **every** node through the exact same
grade, so the LUT *is* the grade. Order: linearize → WB → exposure → re-encode →
gentle contrast → clamp. The preview's "after" is produced by applying the **actual baked
LUT** with hand-written trilinear interpolation, so it honestly previews Lumetri.
(`lut.py`.)

---

## Assumptions & limitations (honest list)

- **Video color decode**: ffmpeg's YUV→RGB uses the clip's color matrix/range defaults.
  For relative diagnosis (warm? clipping?) this is robust; absolute numbers on exotic
  footage may drift. SDR / Rec.709-ish material is the assumption.
- **8-bit pipeline**: frames are analyzed at 8 bits. HDR / log / 10-bit nuance isn't modeled.
- **Temp/Tint numbers are approximate** (see above).
- **Gray-world** (no `--neutral`) is a guess and can be fooled by strongly colored scenes.
- **Auto skin detection** without cv2 uses a YCbCr heuristic; for reliability, pass `--skin`.

---

## Tests

```bash
python3 -m pytest tests/ -q
```
The suite includes a **ground-truth test**: it synthesizes a frame with a *known* injected
color cast + exposure, then asserts gradekit recovers the inverse, that the corrected
neutral patch reads neutral, that clipping is detected, and that the `.cube` is valid.

## License

MIT.
