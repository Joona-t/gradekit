---
name: premiere-grade-bot
description: >
  Use computer-use (screen control) to apply a gradekit color grade to a clip in Adobe
  Premiere Pro by loading a .cube LUT through Lumetri → Creative → Look → Browse. Use when
  the user wants to "fix the color / apply the grade / apply the LUT in Premiere",
  "control Premiere", or "auto-grade in Premiere". Pairs with gradekit (which produces the
  .cube). macOS, Premiere Pro 2026 (`/Applications/Adobe Premiere Pro 2026`).
---

# premiere-grade-bot

Drive Adobe Premiere Pro via the **computer-use** MCP to apply a color grade. This is GUI
automation — it is **vision-guided and verified at every step**, never blind coordinate
clicking.

## Design decision (read first)

**NEVER drag Lumetri sliders** — they are tiny scrub controls and screen-control mis-hits
them constantly. There are two reliable, keyboard/menu-driven input methods; pick per the
user's preference (default: **Method A**, since they asked to type values):

- **Method A — type the Basic values.** In Lumetri → **Basic Correction**, click each
  numeric value, select-all (**Cmd+A**), `type` the number, press **Return/Tab**. gradekit
  prints exact Lumetri Basic numbers (Temperature, Tint, Exposure, Contrast, and the
  Highlights/Whites/Shadows/Blacks "dial" values when there's clipping). Deterministic, and
  the result stays **visible + tweakable** in the Basic panel.
- **Method B — load the .cube via Creative → Look → Browse…**. One menu-driven action that
  carries the whole baked grade (WB + exposure + contrast). A single step, but opaque (lives
  under "Look"). Use when the user wants one-click rather than visible numbers.

**Always apply to an ADJUSTMENT LAYER** placed on the track above all clips, so the entire
timeline is graded at once and the original footage stays untouched.

Still brittle GUI automation: screenshot before every click, verify the expected state, and
**abort + report** if the screen doesn't look right rather than clicking on.

## Tools

computer-use MCP (`mcp__computer-use__*`). If deferred, load them all in one call:
`ToolSearch { query: "computer-use", max_results: 30 }`. Premiere is a **native app → "full"
tier** (clicks + typing allowed). The macOS open-panel is hosted by Premiere (frontmost),
so Premiere access covers it.

## Preconditions (confirm with the user before driving)

1. Premiere Pro is open with the **project loaded** and the **target on the timeline**.
2. There is a **selected clip or (better) an adjustment layer** above all clips to receive
   the grade. Applying to an adjustment layer grades the whole timeline at once.
3. A gradekit **.cube** exists for this footage. If not, make it first:
   ```bash
   cd /path/to/gradekit && . .venv/bin/activate
   python3 -m gradekit analyze "<CLIP.mov>" --lut "<OUT>.cube"
   ```
   (e.g. `~/Downloads/look.cube`)

Because this writes into the user's live project, **never start clicking until the user
confirms the project/clip is ready.** When unsure what's selected, screenshot and ask.

## Procedure

> Take a `screenshot` before AND after every numbered step. Proceed only if the prior step
> produced the expected state. Prefer keyboard over mouse wherever possible.

0. **Access.** `request_access(["Adobe Premiere Pro 2026"])` (match the installed
   `Adobe Premiere Pro *` app). `open_application("Adobe Premiere Pro 2026")` to bring it
   front. Screenshot — confirm a project + timeline are open.
1. **Color workspace** (makes the Lumetri panel's location predictable). Click **Color** in
   the workspace bar, or menu **Window → Workspaces → Color**. Screenshot — confirm the
   **Lumetri Color** panel is visible on the right.
2. **Adjustment layer.** Use an existing adjustment layer spanning all clips, or make one:
   in the **Project** panel click the **New Item** button → **Adjustment Layer…** → OK, then
   drag it onto an empty video track **above all clips** and trim/extend it to cover the
   whole timeline. Screenshot to confirm it spans the clips.
3. **Select the adjustment layer.** Click it once on the timeline (highlighted). Screenshot —
   the Lumetri panel must show live (non-greyed) controls targeting that layer.
4. **Apply the grade — Method A (type Basic values, default):**
   a. In Lumetri Color, click the **Basic Correction** header to expand it. Screenshot.
   b. For EACH value in the "Values to type" table below: click its numeric field (a precise
      `left_click` on the number, or double-click to enter edit mode), `key` **Cmd+A** to
      select, `type` the number (include the sign, e.g. `-30`, `+3`, `-0.8`), press
      **Return**. Screenshot after each field — confirm the field shows the value AND the
      Program monitor shifts. Do them top-to-bottom: White Balance (Temperature, Tint) →
      Tone (Exposure, Contrast, then Highlights/Shadows/Whites/Blacks if listed).
   c. Never drag. If a field won't take focus, double-click it, retry once, else report.
   **— or Method B (load the .cube):** open **Creative**, click the **Look** dropdown →
   **Browse…**, in the open panel press **Cmd+Shift+G**, `type` the `.cube` path
   (e.g. `~/Downloads/look.cube`), **Return**, then **Open**.
5. **Verify.** Screenshot. Confirm the Program monitor visibly changed (cooler, less blown
   out) and the Basic fields show the typed numbers (Method A) or the Look shows the LUT
   (Method B). If nothing changed, report — do not retry blindly.
6. **Report.** State exactly what was applied (which values/LUT, onto the adjustment layer)
   with an after `screenshot` as proof. Remind the user to **Cmd+S** — but let THEM save.

## Values to type (Method A) — from gradekit

Whatever clip is being graded, get its numbers from `gradekit analyze` ("Lumetri → Basic"
lines). For the current Outlast Ep1 footage:

| Field (Basic Correction) | IMG_7758 (take 1) | IMG_7756 (take 2) |
| --- | --- | --- |
| White Balance · **Temperature** | **-30** | **-38** |
| White Balance · **Tint** | **+3** | **+2** |
| Tone · **Exposure** | **-0.8** | **-0.7** |
| Tone · **Contrast** (gentle, optional) | **+10** | **+10** |

These remove the warm/amber cast and bring the overexposed midtones down. Exposure is a
measured target — nudge by eye if the user wants. (No highlight/shadow clipping was flagged
on this footage, so no Highlights/Whites/Shadows/Blacks moves are needed; for footage that
*does* clip, gradekit prints those "dial" values too — type them the same way.)

## Multiple takes / clips

gradekit may produce a slightly different LUT per take (e.g. `outlast-ep1-fix.cube` vs
`-take2.cube`). Apply the matching LUT to each take's clips, or apply one to an adjustment
layer and tweak Exposure per the other take. Confirm which clip is selected before each
apply.

## Failure handling

- **Can't find Look/Browse:** the Lumetri panel may be collapsed/scrolled — scroll the panel,
  re-expand Creative, screenshot, retry once; else report.
- **Open panel path entry fails:** navigate the dialog manually (sidebar → Downloads), or
  report the exact path for the user to paste.
- **Wrong/greyed Lumetri panel:** no clip selected — go back to step 2.
- **Anything unexpected on screen:** stop and report with a screenshot. Do not "click around."

## Field-tested gotchas (PP 2026 — learned from a live run)

1. **File → New → Adjustment Layer is greyed unless the PROJECT PANEL is active.** Click an
   empty spot in the Project panel first, THEN open File → New → Adjustment Layer.
2. **A dropped adjustment layer lands where you release the mouse, not at 0.** After dropping
   it on V2, drag it left so its start snaps to the playhead/sequence start (put the playhead
   at 0 with Home first to give a snap target).
3. **Do NOT use Extend-Edit (E) to span the layer — it acts on the TARGETED track (V1), not
   the selected clip.** Instead: right-click the adjustment layer → **Speed/Duration…** and
   TYPE the full sequence duration (e.g. `00:31:00:12`, the sequence total shown by the
   Program monitor). Deterministic, no off-screen edge-dragging. Speed/Duration is near the
   BOTTOM of a long context menu — scroll down to it.
4. **Keyboard zoom (`\`, `-`) may do nothing** depending on focus — use the timeline's bottom
   **zoom scrollbar handles** to zoom out (see whole sequence) / in (grab small clips).
5. **Decimal separator may be a COMMA** (locale-dependent: fields read `0,0`). Type decimals
   with a comma (`-0,75`); the field rounds to one decimal (shows `-0,8`).
6. **Lumetri value entry: DOUBLE-CLICK the number → type → Return.** A single click + Cmd+A
   did not enter edit mode. Same for the Speed/Duration timecode field.
7. **Exposure/Contrast live under the collapsed "Light" section**, which sits below the fold —
   expand Light and **scroll the Lumetri panel down** to reach them.
8. **Multiple takes on one timeline:** a single spanning adjustment layer applies ONE grade to
   all of them. If per-take values differ, either use one averaged grade (fine when close) or
   make one adjustment layer per take's range.

## Why not ExtendScript / a preset?

Those are sturdier (and gradekit could emit a `.prfpset`), but the user chose screen-control.
This skill is the least-brittle way to honor that: one menu-driven LUT load, fully verified,
zero slider dragging. If it proves flaky in practice, offer the one-drag `.prfpset` again.
