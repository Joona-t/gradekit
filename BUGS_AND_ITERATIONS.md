# Bugs & Iterations

Running log of defects found and fixes/iterations landed. Newest first.

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
