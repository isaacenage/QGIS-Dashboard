# -*- coding: utf-8 -*-
"""InspectorPanel — a right-edge editor panel, à la ArcGIS Experience Builder.

The tile editors (Configure / Connections / Tile appearance) and the header
editor no longer open as modal dialogs that block the canvas. They are hosted,
one at a time, in this panel which **overlays the right strip of the canvas**
(it is a manually-positioned child of the window's central area, raised above
the page view, never in a layout). The left icon rail is always clear of it.

Commit model (the window supplies the callbacks):
  * **OK** runs ``on_commit`` — keep the live edits.
  * **Cancel** / the header **✕** / closing runs ``on_cancel`` — revert.
  * Opening another editor while one is open implicitly **commits** the open
    one first (its live changes are already visible, so moving on keeps them).
  * If the edited subject (a tile) is removed, the panel is dropped *without*
    running either callback (they would touch a destroyed object).
"""

from qgis.PyQt.QtCore import (
    Qt, QPoint, QRect, QEasingCurve, QPropertyAnimation, pyqtSignal,
)
from qgis.PyQt.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QPushButton,
    QWidget,
)

from .theme import CHROME

PANEL_WIDTH = 360


class InspectorPanel(QFrame):
    """A right-edge overlay hosting one editor form at a time."""

    closed = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.setObjectName("inspectorPanel")
        self._theme = theme
        self._content = None
        self._subject = None
        self._on_commit = None
        self._on_cancel = None
        self._anim = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- header: title + close ✕ ----
        header = QFrame()
        header.setObjectName("inspectorHeader")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(16, 12, 10, 12)
        self._title = QLabel("")
        self._title.setObjectName("inspectorTitle")
        hrow.addWidget(self._title, 1)
        self._close_btn = QToolButton()
        self._close_btn.setObjectName("inspectorClose")
        self._close_btn.setText("✕")
        self._close_btn.setAutoRaise(True)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close (discard changes)")
        self._close_btn.clicked.connect(self._cancel)
        hrow.addWidget(self._close_btn)
        root.addWidget(header)

        # ---- content slot ----
        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(16, 14, 16, 14)
        root.addWidget(self._content_host, 1)

        # ---- footer: Cancel | OK ----
        footer = QFrame()
        footer.setObjectName("inspectorFooter")
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(16, 10, 16, 12)
        frow.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("variant", "secondary")
        self._cancel_btn.clicked.connect(self._cancel)
        frow.addWidget(self._cancel_btn)
        self._ok_btn = QPushButton("OK")
        self._ok_btn.clicked.connect(self._commit)
        frow.addWidget(self._ok_btn)
        root.addWidget(footer)

        self.apply_theme(theme)
        self.hide()

    # ---- opening / closing ---------------------------------------------

    def open_editor(self, title, content, on_commit=None, on_cancel=None,
                    subject=None, commit_label="OK"):
        """Show *content* in the panel, replacing any open editor (committing
        it first)."""
        # implicit-commit the editor that's already open
        self._finish(commit=True)

        self._title.setText(title)
        self._ok_btn.setText(commit_label)
        self._content = content
        self._subject = subject
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._content_layout.addWidget(content)

        self.show()
        self.raise_()
        self.reposition()
        self._animate_in()

    def close_active(self, commit=True):
        """Close the open editor (used on page switch / dashboard reset)."""
        self._finish(commit=commit)

    def discard_if_subject(self, subject):
        """Drop the panel without running callbacks if it edits *subject*
        (its underlying object is being destroyed)."""
        if self._content is not None and self._subject is subject:
            self._on_commit = None
            self._on_cancel = None
            self._finish(commit=False)

    def _commit(self):
        self._finish(commit=True)

    def _cancel(self):
        self._finish(commit=False)

    def _finish(self, commit):
        if self._content is None:
            return
        cb = self._on_commit if commit else self._on_cancel
        content = self._content
        # clear state first so a re-entrant open_editor() lands cleanly and the
        # callback can't be run twice
        self._content = None
        self._subject = None
        self._on_commit = None
        self._on_cancel = None
        try:
            if callable(cb):
                cb()
        finally:
            self._content_layout.removeWidget(content)
            content.setParent(None)
            content.deleteLater()
            self.hide()
            self.closed.emit()

    # ---- geometry / animation ------------------------------------------

    def reposition(self):
        """Pin to the right edge of the parent (over the canvas), full height."""
        p = self.parentWidget()
        if p is None:
            return
        self.setGeometry(QRect(p.width() - PANEL_WIDTH, 0,
                               PANEL_WIDTH, p.height()))

    def _animate_in(self):
        p = self.parentWidget()
        if p is None:
            return
        end = QPoint(p.width() - PANEL_WIDTH, 0)
        start = QPoint(p.width(), 0)
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(180)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim   # keep a reference so it isn't GC'd

    # ---- theming -------------------------------------------------------

    def apply_theme(self, theme):
        # The inspector is CHROME — it must read identical no matter which
        # dashboard theme/preset is active, so it uses the fixed CHROME palette
        # rather than the (canvas-only) theme colors.
        self._theme = theme
        self.setStyleSheet("""
#inspectorPanel {{ background:{chrome}; border-left:1px solid {border}; }}
#inspectorHeader {{ background:{chrome}; border-bottom:1px solid {border}; }}
#inspectorTitle {{ color:{text}; font-weight:700; }}
#inspectorFooter {{ background:{chrome}; border-top:1px solid {border}; }}
QToolButton#inspectorClose {{
    border:none; background:transparent; border-radius:6px; padding:2px 6px;
    color:{muted}; font-size:15px;
}}
QToolButton#inspectorClose:hover {{ background:{brand_soft}; color:{accent}; }}
""".format(chrome=CHROME["bg"], border=CHROME["border"], text=CHROME["text"],
           muted=CHROME["muted"], accent=CHROME["accent"],
           brand_soft=CHROME["brand_soft"]))
