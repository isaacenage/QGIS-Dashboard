# Undo / Redo for the dashboard

**Date:** 2026-06-18
**Status:** Approved

## Goal

Add Undo / Redo to the dashboard editor, exposed as two new buttons on the
left icon rail and as keyboard shortcuts. Coverage is **everything that
persists in the v3 layout dict** — tile move/resize/add/remove, configure,
appearance, connections, page add/delete/rename/reorder, grid, canvas size,
gap, theme, and the Build/Use lock.

## Approach: whole-dashboard snapshots

The dashboard already serializes to one v3 dict via `_build_layout_dict()` and
rebuilds from one via `_apply_layout_dict()`. Rather than write per-operation
inverse commands, history is a stack of these snapshots: undo/redo re-applies a
stored snapshot. Consequence: undo restores the **entire** dashboard to a prior
point (not a per-tile history) — the standard, predictable behavior.

History is **session-only** (never persisted, like zoom). It is seeded when a
dashboard is loaded or created and reset on each load/new.

## Components

### `history.py` (new, Qt-free, unit-tested)

A `History` class holding `_undo` (past), `_redo` (future), `_current`. Each
snapshot is a deep copy of the layout dict, normalized via a JSON round-trip so
equality comparison is reliable.

- `record(snapshot)` — if equal to `_current`, no-op (return `False`); else push
  `_current` onto `_undo`, clear `_redo`, set `_current = snapshot`, return
  `True`. `_undo` is capped at `MAX_DEPTH = 50` (drop oldest).
- `undo()` / `redo()` — move `_current` across the stacks; return the snapshot to
  apply (or `None` when empty).
- `can_undo()` / `can_redo()` — drive button enablement.

Tested in `test/test_history.py` on plain dicts (no QGIS needed).

### Capture mechanism (`window.py`)

A debounced `_record_history()` (≈120 ms `QTimer`, coalescing slider drags /
rapid edits into one entry) builds the current layout dict and calls
`history.record(...)`. Wired to every persisting mutation:

- each page's `canvas.layoutChanged` (connected when a page is created),
- `bus.connectionsChanged`, `bus.themeChanged`,
- explicit calls after page add/delete/rename/reorder, grid change, canvas-size
  change, gap change, lock toggle, tile reconfigure / appearance apply.

A `self._restoring` guard suppresses recording while `_apply_layout_dict()`
replays a snapshot (otherwise undo would re-record itself).

### Apply (`window.py`)

`undo()` / `redo()`: set guard → `_apply_layout_dict(snapshot)` → refresh button
enabled-state → clear guard. No-ops / disabled on the Start screen (no
dashboard).

### Rail UI (`sidebar.py` + `window.py`)

Two new buttons in their own group, placed after the Add-element / Add-page
group (separator · Undo · Redo · separator · then Zoom). `Sidebar` gains a way
to fetch/enable a button by icon key so the window can grey them out when
`can_undo` / `can_redo` is false.

### Icons (`icons.py`)

Two new `_stroke()` glyphs `undo` / `redo` — mirrored curved return arrows in
the existing 1.0-stroke rail style. No fitting glyph exists today.

### Shortcuts (`window.py`)

Window-wide `QShortcut`s: **Ctrl+Z** → undo, **Ctrl+Y** and **Ctrl+Shift+Z** →
redo.

## Plumbing

Register `history.py` and `test/test_history.py` in both `pb_tool.cfg`
(`python_files`) and `Makefile` (`PY_FILES` / `SOURCES`) per repo convention.

## Out of scope

- Per-tile / granular undo (snapshots are whole-dashboard by design).
- Persisting history across sessions.
- A visible history panel / multi-step preview.
