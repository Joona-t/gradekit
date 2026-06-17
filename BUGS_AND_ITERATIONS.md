# Bugs & Iterations

Running log of defects found and fixes/iterations landed. Newest first.

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
