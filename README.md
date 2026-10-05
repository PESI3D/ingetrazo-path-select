# Path Select — select a path of edges by clicking along it, for IngeTrazo

Click a few points along a contour and the **shortest way along the edges** between your clicks is filled in and selected — like the «Smart Path Selection» of Profile Builder for SketchUp. Handy for contour lines, outlines and paths in imported plans (DXF/DWG/PDF) that arrive as hundreds of single segments.

[Deutsch → LIESMICH.md](LIESMICH.md)

![Path Select](screenshot.webp)

## Installation
1. In IngeTrazo: **Extensions ▸ Open plugins folder** (Windows: `%APPDATA%\ingetrazo\plugins\`, Linux: `~/.local/share/ingetrazo/plugins/`).
2. Copy `path_select_tool.py` into that folder.
3. Restart IngeTrazo → **Extensions ▸ Path Select** (Alt+C).

Requires IngeTrazo ≥ 0.5 (extension API 2).

## How to use
1. **Click an edge** — the path starts there.
2. **Move the mouse to another edge** — the shortest way from your last click to that edge is shown in blue.
3. **Click** — that part is added (orange). Repeat as often as you like; the path closes when it reaches its own start.
4. The path **is the selection** from the first click on: Ctrl+C, Move or Delete work right away.
5. **Enter** or a double-click ends the path; the next click starts a new one.

- **Backspace** takes back the last part, **Esc** drops the path and gives back the selection you had before.
- **Ctrl / Shift / Shift+Ctrl** on the first click add the path to, toggle it in, or remove it from the current selection — as with Select.
- The status bar shows the number of edges and the length, with the preview.
- **Right-click ▸ Select Contour** grows the selected edges along their chains (up to the next junction).
- The tool stays on until you pick another one (Space = Select).

## Changelog
- **1.0** — first release.

## Licence
GPL-3.0-or-later · © 2026 Pesi (pesi3d.de) · [Impressum](https://pesi3d.de)

Not affiliated with or endorsed by mind.sight.studios or Trimble Inc.; «Profile Builder» and «SketchUp» are named only to describe the workflow.
