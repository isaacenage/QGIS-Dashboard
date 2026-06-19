# -*- coding: utf-8 -*-
"""Undo / redo history for the dashboard — a stack of whole-dashboard snapshots.

The dashboard already serializes to one v3 layout dict (``_build_layout_dict``)
and rebuilds from one (``_apply_layout_dict``). Rather than write per-operation
inverse commands, history is just a stack of those dicts: undo/redo re-applies a
stored snapshot. A consequence is that undo restores the **entire** dashboard to
a prior point — a single, predictable timeline rather than a per-tile history.

This module is deliberately **Qt-free and pure** so it can be unit-tested on
plain dicts without QGIS (see ``test/test_history.py``). Each snapshot is
normalized via a JSON round-trip on the way in, so equality comparison (used to
drop no-op records) is reliable regardless of dict key ordering.
"""

import copy
import json

# How many undo steps to keep. Older entries fall off the bottom of the stack.
MAX_DEPTH = 50


def _normalize(snapshot):
    """A canonical deep copy of *snapshot* (sorted keys) for stable equality."""
    return json.loads(json.dumps(snapshot, sort_keys=True))


class History:
    """A bounded undo/redo timeline over dashboard-layout snapshots.

    ``current`` is the live state; :meth:`record` pushes the previous live state
    onto the undo stack. :meth:`undo`/:meth:`redo` walk the timeline and return
    the snapshot the caller should apply (or ``None`` at an end).
    """

    def __init__(self, initial=None, max_depth=MAX_DEPTH):
        self._max_depth = max(1, int(max_depth))
        self._undo = []
        self._redo = []
        self._current = _normalize(initial) if initial is not None else None

    # ---- introspection ----

    @property
    def current(self):
        """A deep copy of the live snapshot (``None`` before anything is seeded)."""
        return copy.deepcopy(self._current)

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def __len__(self):
        return len(self._undo)

    # ---- mutation ----

    def record(self, snapshot):
        """Record *snapshot* as the new live state.

        No-op (returns ``False``) when it equals the current state — so the many
        signals a single edit fires collapse into at most one entry, and a
        replayed undo/redo does not re-record itself. Otherwise the previous
        state is pushed onto the undo stack, the redo stack is cleared, and the
        depth cap is enforced.
        """
        snap = _normalize(snapshot)
        if snap == self._current:
            return False
        if self._current is not None:
            self._undo.append(self._current)
            if len(self._undo) > self._max_depth:
                self._undo.pop(0)
        self._redo = []
        self._current = snap
        return True

    def undo(self):
        """Step back one state; return the snapshot to apply, or ``None``."""
        if not self._undo:
            return None
        self._redo.append(self._current)
        self._current = self._undo.pop()
        return copy.deepcopy(self._current)

    def redo(self):
        """Step forward one state; return the snapshot to apply, or ``None``."""
        if not self._redo:
            return None
        self._undo.append(self._current)
        self._current = self._redo.pop()
        return copy.deepcopy(self._current)
