# Bugs & Iterations

Running log of defects found and fixes/iterations landed. Newest first.

## ITER-003 — `--brightest`: grade the worst-case frame, not an "average" one (2026-06-25)
**What hurt:** a 20-min talking-head (light furry hood + cream sweater, varying brightness as the
subject leans in/out and raises hands) was graded off gradekit's default ~10%-in frame. On that calm
frame gradekit reported **"✓ Exposure and contrast look fine"**, so the applied grade used a gentle
Highlights −12 / Shadows +25. Result on the BRIGHT frames: the white wardrobe clipped to a featureless
white blob and the image looked washed out. Joona (correctly) called the grade "horrible".
**Root cause:** gradekit analyzes a SINGLE frame. If that frame isn't the brightest, highlight/exposure
problems that only appear on the bright frames are invisible, so the recommendation under-corrects.
**Fix (in code):** added `--brightest [N]` (default N=9). It samples N frames across the clip
(`extract_brightest_frame`), scores each by 99.5th-pct Rec.709 luma (`_luma99`, ignores speckle), and
grades the BRIGHTEST — so highlight rolloff protects the worst case; calmer frames just sit a touch lower.
**Verified on IMG_7889:** default frame @133s → "Exposure looks fine"; `--brightest` jumped to @817s →
"✗ Overexposed, Exposure −0.3". Tests: 24 passed (added `tests/test_frameio.py` for the luma scoring).
**Standing grading rule (also in the LoveSpark notes):** for a bright / light-wardrobe subject, grade the
BRIGHTEST frame and recover highlights AGGRESSIVELY (Whites/Highlights −40…−60, restrained Shadows ≈+6,
slight Blacks for contrast) — gentle values leave a clipped blob. The fix that worked here: Temp −25,
Tint −4, Contrast +12, Highlights −60, Whites −45, Shadows +6, Blacks −6.
**Still open (v_next):** gradekit recommends Whites/Highlights pulls only when `blown_pct` is high; a
"bright-but-not-clipping" subject (hood at ~90–95%, not 255) still reads as a blob yet trips no
recommendation. Bias the highlight recommendation on the brightest frame's white-point, not just on
the literal clip count.

## BUG-002 — Exposure blows out a bright subject on a dark background (2026-06-24)
**Symptom:** on a real shot (a person in a white hoodie in front of a dark bookshelf),
gradekit prescribed Exposure **+1.5 stops**, which clipped the subject to pure white when
applied in Premiere. The grade was unusable and had to be hand-corrected.
**Root cause:** `analyze_exposure` meters exposure off the **whole-frame median** luminance
(`np.median(luma_lin)` → `log2(0.18/median)`). A small bright subject in front of a large
dark field drags the median down, so the math reads the frame as badly underexposed and
prescribes a big lift — which blows the (already bright) subject.
**Fix:** added a **highlight-safe cap** (`exposure.py`): any *positive* lift is capped so the
brightest meaningful detail (99.5th pct of linear luma) lands no higher than `HILIGHT_CEIL`
(0.90). Pulls-down for genuinely over-bright frames are untouched. Verified: the same shot now
reports "✓ Exposure and contrast look fine" instead of +1.5; 22/22 tests still green.
**Prevention:** exposure must never push existing highlights into clipping. (Future v_next:
also bias the target toward the detected skin/subject region, since gradekit already finds it.)

## BUG-001 — Hardcoded home-directory paths leaked into the public repo (2026-06-17)
**Symptom:** after going public (ITER-002), the maintainer's macOS home path (`/Users/<user>/…`,
exposing the local username) was visible in `README.md` ("from anywhere" install example) and
`skills/premiere-grade-bot/SKILL.md` (a `cd`
example + a `.cube` browse-path example). Spotted by Joona reviewing the rendered README.
**Root cause:** docs were authored against the live local checkout and copied absolute paths
verbatim. `How it works.html` already used `/path/to/gradekit` (correct); the older README/SKILL
text predated that convention.
**Fix:** genericized all home paths to `/path/to/gradekit` and `~/Downloads/look.cube`; also
dropped the project-specific `outlast-ep1-*.cube` example names from the public skill doc.
`LICENSE` keeps "Joona Tyrninoksa" — that's the intentional MIT copyright attribution, not a leak.
**Prevention:** never paste an absolute `/Users/<name>/…` path into a file that ships in a repo —
use `/path/to/…`, `~/…`, or `$PWD`. (Worth a pre-publish grep: `git grep -nE "/Users/"`.)
**Note:** this scrubs the working tree; the string still exists in git history (commits before
this one) — a history rewrite + force-push is the only way to purge that, and needs explicit
sign-off + a backup first.

## ITER-002 — De-branded, made public, shipped a manual (2026-06-17)
**What:** Released gradekit as a standalone OSS tool and gave it a self-contained manual.
- **De-brand + publish:** renamed the repo `lovespark-gradekit` → `gradekit` and flipped it
  **public**. gradekit is a general creator/agent tool, not part of the neurodivergent-consumer
  LoveSpark suite — so it follows the `godot-dev-bridge` precedent (drop the `lovespark-` prefix).
  Secret-scanned clean before going public (no keys/credentials).
- **`How it works.html`:** a single self-contained HTML manual (no external assets) for devs,
  users, and agents — color science walkthrough with an SVG pipeline diagram, CLI reference,
  the report format, an **editor-agnostic "apply the LUT"** table (Premiere/Resolve/FCP/AE/
  Photoshop/OBS/ffmpeg), and a **"using it with your agents"** section (exact venv invocation,
  a paste-in capsule, the no-API rule, the premiere-grade-bot handoff).
- **Editor-agnostic framing:** the `.cube` is a standard 3D LUT; only the report *wording*
  ("Lumetri") leans Premiere. Updated the pyproject description to say so.
- **Version:** bumped `0.1.0` → `0.1.1` (`__init__.py` + `pyproject.toml` kept in sync).
**Defect caught & fixed during build:** the overview `.note` block had a stray `</p>` (no
matching `<p>`); HTML-parser validation flagged it (browser-tolerated but wrong). Removed it —
manual now parses with zero nesting errors, all 15 nav anchors resolve, JS passes `node --check`.
**Verification:** `pytest -q` → 22/22 green; `gradekit --version` → 0.1.1; HTML well-formedness +
anchor-resolution + self-containment checks all pass.

## ITER-001 — Repo created; premiere-grade-bot companion added (2026-06-17)
**What:** Put gradekit under version control for the first time (it had lived as an
unversioned local folder) and added its companion Claude Code skill.
- `skills/premiere-grade-bot/SKILL.md`: computer-use bot that applies a gradekit grade in
  Adobe Premiere Pro — creates a full-sequence adjustment layer and types the
  Temperature/Tint/Exposure/Contrast into Lumetri Basic (no slider dragging), or loads the
  baked `.cube` via Creative → Look. Verified live on Premiere Pro 2026.
- Added `LICENSE` (MIT — matches the README's stated license).
**Field-tested gotchas captured in the skill** (from the first live Premiere run): File → New →
Adjustment Layer is greyed unless the Project panel is active; a dropped adjustment layer lands
at the drop point, not 0 (snap it left); use right-click → Speed/Duration to span the sequence
(Extend-Edit `E` acts on the targeted track, not the selected clip); Lumetri fields are
double-click-to-edit; the locale here uses comma decimals (`-0,75`).
