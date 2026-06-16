# -*- coding: utf-8 -*-
"""The Start / Home screen shown inside the canvas area.

QGIS greets you with recent projects as cards; the Summarizer plugin does the
same for its dashboards. This view is our equivalent: when a QGIS project has no
dashboard yet (and any time the **Home** rail button is pressed), the canvas
shows a scrollable wall of cards —

* two **action cards** — *New Dashboard* and *Open from file…* — and
* one **recent card** per recently saved/opened ``.qdash`` file (branded logo
  preview, name, elided path, last-modified date).

Everything is themed through :class:`~theme.Theme` (soft ``theme.border``
hairlines only — no dark outlines, per the codebase rule) and restyled on
``themeChanged`` via :meth:`StartView.apply_theme`.
"""

import os

from qgis.PyQt.QtCore import Qt, pyqtSignal, QDateTime, QSize
from qgis.PyQt.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
    QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
)
from qgis.PyQt.QtGui import QColor

from .icons import monochrome_icon, logo_pixmap

CARD_W = 224
CARD_H = 208
CARD_GAP = 16


class _BaseCard(QFrame):
    """A clickable, themed card. Subclasses fill in the body."""

    clicked = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_W, CARD_H)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(15, 23, 42, 30))
        self.setGraphicsEffect(shadow)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and \
                self.rect().contains(event.pos()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _card_qss(self, object_name):
        t = self._theme
        return (
            "QFrame#%(n)s { background:%(bg)s; border:1px solid %(border)s;"
            " border-radius:%(r)dpx; }"
            "QFrame#%(n)s:hover { background:%(soft)s; border-color:%(accent)s; }"
            % {"n": object_name, "bg": t.surface_bg, "border": t.border,
               "r": int(t.radius), "soft": t._brand_soft(), "accent": t.accent}
        )


class _ActionCard(_BaseCard):
    """A large call-to-action card: tinted glyph + title + subtitle."""

    def __init__(self, theme, icon_key, title, subtitle, parent=None):
        super().__init__(theme, parent)
        self.setObjectName("startActionCard")
        self._icon_key = icon_key

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 16)
        lay.setSpacing(10)

        self._chip = QLabel(self)
        self._chip.setObjectName("startActionChip")
        self._chip.setFixedSize(46, 46)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._chip)
        lay.addStretch(1)

        self._title = QLabel(title, self)
        self._title.setObjectName("startActionTitle")
        self._title.setWordWrap(True)
        lay.addWidget(self._title)

        self._subtitle = QLabel(subtitle, self)
        self._subtitle.setObjectName("startActionText")
        self._subtitle.setWordWrap(True)
        lay.addWidget(self._subtitle)

        self.apply_theme(theme)

    def apply_theme(self, theme):
        self._theme = theme
        t = theme
        self._chip.setPixmap(monochrome_icon(self._icon_key, "#ffffff")
                             .pixmap(QSize(24, 24)))
        self.setStyleSheet(
            self._card_qss("startActionCard")
            + ("QLabel#startActionChip { background:%(accent)s;"
               " border-radius:12px; }"
               "QLabel#startActionTitle { color:%(text)s; font-size:16px;"
               " font-weight:600; background:transparent; }"
               "QLabel#startActionText { color:%(muted)s; font-size:12px;"
               " background:transparent; }"
               % {"accent": t.accent, "text": t.text, "muted": t.text_muted}))


class _RecentCard(_BaseCard):
    """A recent ``.qdash`` card: logo preview, name, elided path, date."""

    openRequested = pyqtSignal(str)

    def __init__(self, theme, path, name, updated_at, parent=None):
        super().__init__(theme, parent)
        self.setObjectName("startRecentCard")
        self._path = path
        self.setToolTip(path)
        self.clicked.connect(lambda: self.openRequested.emit(self._path))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._preview = QFrame(self)
        self._preview.setObjectName("startRecentPreview")
        self._preview.setFixedHeight(112)
        prow = QVBoxLayout(self._preview)
        prow.setContentsMargins(0, 0, 0, 0)
        self._logo = QLabel(self._preview)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setPixmap(logo_pixmap(44))
        prow.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._preview)

        body = QWidget(self)
        body.setObjectName("startRecentBody")
        brow = QVBoxLayout(body)
        brow.setContentsMargins(14, 12, 14, 12)
        brow.setSpacing(4)

        self._name = QLabel(name, body)
        self._name.setObjectName("startRecentTitle")
        brow.addWidget(self._name)

        self._meta_full = self._meta_text(path, updated_at)
        self._meta = QLabel(self._meta_full, body)
        self._meta.setObjectName("startRecentText")
        self._meta.setWordWrap(False)
        brow.addWidget(self._meta)
        brow.addStretch(1)
        lay.addWidget(body, 1)

        self.apply_theme(theme)

    def _meta_text(self, path, updated_at):
        when = _friendly_date(updated_at)
        folder = os.path.basename(os.path.dirname(path)) or path
        parts = [p for p in (folder, when) if p]
        return "  ·  ".join(parts)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def showEvent(self, event):
        super().showEvent(event)
        self._elide()

    def _elide(self):
        fm = self._meta.fontMetrics()
        self._meta.setText(fm.elidedText(
            self._meta_full, Qt.TextElideMode.ElideRight,
            max(40, self._meta.width())))

    def apply_theme(self, theme):
        self._theme = theme
        t = theme
        self.setStyleSheet(
            self._card_qss("startRecentCard")
            + ("QFrame#startRecentPreview { background:%(soft)s; border:none;"
               " border-top-left-radius:%(r)dpx; border-top-right-radius:%(r)dpx; }"
               "QWidget#startRecentBody { background:transparent; border:none; }"
               "QLabel#startRecentTitle { color:%(text)s; font-size:13px;"
               " font-weight:600; background:transparent; }"
               "QLabel#startRecentText { color:%(muted)s; font-size:11px;"
               " background:transparent; }"
               % {"soft": t._brand_soft(), "r": int(t.radius),
                  "text": t.text, "muted": t.text_muted}))


class _CardGrid(QWidget):
    """Holds fixed-size cards in a grid that reflows to the available width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(CARD_GAP)
        self._grid.setVerticalSpacing(CARD_GAP)
        self._cols = 0

    def set_cards(self, cards):
        for old in self._cards:
            self._grid.removeWidget(old)
            old.setParent(None)
            old.deleteLater()
        self._cards = list(cards)
        self._cols = 0
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        if not self._cards:
            return
        cols = max(1, (self.width() + CARD_GAP) // (CARD_W + CARD_GAP))
        if cols == self._cols:
            return
        self._cols = cols
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols,
                                 Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignTop)


class StartView(QWidget):
    """Recent-projects landing screen for :class:`~window.DashboardWindow`."""

    continueRequested = pyqtSignal()
    newRequested = pyqtSignal()
    openFileRequested = pyqtSignal()
    openRecentRequested = pyqtSignal(str)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.setObjectName("startView")
        self._theme = theme

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("startScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        content = QWidget()
        content.setObjectName("startContent")
        col = QVBoxLayout(content)
        col.setContentsMargins(40, 36, 40, 36)
        col.setSpacing(14)

        self._heading = QLabel("QGIS Dashboard")
        self._heading.setObjectName("startHeading")
        col.addWidget(self._heading)
        self._tagline = QLabel("Open a recent dashboard or start a new one.")
        self._tagline.setObjectName("startTagline")
        col.addWidget(self._tagline)

        self._start_label = self._section_label("Start")
        col.addSpacing(8)
        col.addWidget(self._start_label)
        self._actions = _CardGrid(content)
        col.addWidget(self._actions)

        self._recent_label = self._section_label("Recent dashboards")
        col.addSpacing(14)
        col.addWidget(self._recent_label)
        self._empty = QLabel(
            "No saved dashboards yet — create one with New Dashboard, "
            "then Save it from the rail.")
        self._empty.setObjectName("startEmpty")
        self._empty.setWordWrap(True)
        col.addWidget(self._empty)
        self._recents = _CardGrid(content)
        col.addWidget(self._recents)
        col.addStretch(1)

        scroll.setWidget(content)
        self._content = content
        self._scroll = scroll

        self._can_continue = False
        self._build_action_cards()
        self.set_recents([])
        self.apply_theme(theme)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("startSection")
        return lbl

    def _build_action_cards(self):
        # _CardGrid.set_cards destroys the cards it previously held, so the
        # action cards are rebuilt fresh whenever the set changes (rather than
        # held and re-passed, which would reuse freed widgets).
        self._action_cards = []
        self._refresh_actions()

    def _refresh_actions(self):
        """Rebuild the action cards — the Continue card only when a dashboard
        is currently loaded."""
        cards = []
        if self._can_continue:
            cont = _ActionCard(
                self._theme, "home", "Continue current dashboard",
                "Return to the dashboard you're editing.")
            cont.clicked.connect(self.continueRequested.emit)
            cards.append(cont)
        new_card = _ActionCard(
            self._theme, "add_element", "New Dashboard",
            "Start a blank dashboard in this project.")
        new_card.clicked.connect(self.newRequested.emit)
        cards.append(new_card)
        open_card = _ActionCard(
            self._theme, "open", "Open from file…",
            "Open a saved .qdash dashboard file.")
        open_card.clicked.connect(self.openFileRequested.emit)
        cards.append(open_card)
        self._action_cards = cards
        self._actions.set_cards(cards)

    def set_can_continue(self, can_continue):
        can_continue = bool(can_continue)
        if can_continue == self._can_continue:
            return
        self._can_continue = can_continue
        self._refresh_actions()

    def set_recents(self, items):
        """Populate the recent cards from a list of ``{path, name, updated_at}``."""
        cards = []
        for it in items or []:
            card = _RecentCard(
                self._theme, it.get("path", ""), it.get("name", ""),
                it.get("updated_at", ""))
            card.openRequested.connect(self.openRecentRequested.emit)
            cards.append(card)
        self._recent_cards = cards
        self._recents.set_cards(cards)
        self._empty.setVisible(not cards)
        self._recents.setVisible(bool(cards))

    def apply_theme(self, theme):
        self._theme = theme
        t = theme
        self.setStyleSheet(
            "#startView, #startScroll, #startContent { background:%(bg)s; }"
            "#startHeading { color:%(text)s; font-size:22px; font-weight:700;"
            " background:transparent; }"
            "#startTagline { color:%(muted)s; font-size:13px;"
            " background:transparent; }"
            "#startSection { color:%(text)s; font-size:13px; font-weight:600;"
            " background:transparent; }"
            "#startEmpty { color:%(muted)s; font-size:12px;"
            " background:transparent; }"
            % {"bg": t.window_bg, "text": t.text, "muted": t.text_muted})
        for card in getattr(self, "_action_cards", []):
            card.apply_theme(theme)
        for card in getattr(self, "_recent_cards", []):
            card.apply_theme(theme)


def _friendly_date(iso):
    if not iso:
        return ""
    dt = QDateTime.fromString(str(iso), Qt.DateFormat.ISODate)
    if not dt.isValid():
        return ""
    return dt.toString("MMM d, yyyy")
