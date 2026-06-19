# -*- coding: utf-8 -*-
"""Shared per-tile table styling for the list & pivot elements.

Both render a ``QTableWidget`` and expose the same "Table" role in their style
schema (header / row / zebra / gridline typography + colors). This builds the
QSS for that role from an element's ``config["style"]`` (falling back to the
effective theme), so the two elements stay DRY.
"""

from .base import _FONT_FALLBACK


def table_qss(el, theme, selection=True):
    """Return a stylesheet for *el*'s table from its style role + *theme*."""
    header_bg = el.style_get("header_bg", theme.zebra)
    header_color = el.style_get("header_color", theme.text)
    header_font = el.style_get("header_font", theme.font_family)
    header_px = int(el.style_get("header_px", theme.font_size))
    header_weight = int(el.style_get("header_weight", 600))
    row_color = el.style_get("row_color", theme.text)
    row_font = el.style_get("row_font", theme.font_family)
    row_px = int(el.style_get("row_px", theme.font_size))
    zebra = el.style_get("zebra_color", theme.zebra)
    grid = el.style_get("grid_color", theme.border)
    sel = el.style_get("sel_color", theme.selection)
    return (
        'QTableWidget, QTableView {{ background:{surface}; color:{row_color};'
        ' gridline-color:{grid}; border:1px solid {grid}; border-radius:10px;'
        ' alternate-background-color:{zebra}; selection-background-color:{sel};'
        ' selection-color:{row_color}; font-family:"{row_font}", {fb};'
        ' font-size:{row_px}px; }}'
        'QTableView::item, QTableWidget::item {{ padding:4px 8px; }}'
        'QHeaderView::section {{ background:{header_bg}; color:{header_color};'
        ' font-family:"{header_font}", {fb}; font-size:{header_px}px;'
        ' font-weight:{header_weight}; border:none;'
        ' border-right:1px solid {grid}; border-bottom:1px solid {grid};'
        ' padding:6px 10px; }}'
        'QTableCornerButton::section {{ background:{header_bg}; border:none; }}'
        .format(
            surface=theme.surface_bg, row_color=row_color, grid=grid,
            zebra=zebra, sel=sel, row_font=row_font, row_px=row_px,
            header_bg=header_bg, header_color=header_color,
            header_font=header_font, header_px=header_px,
            header_weight=header_weight, fb=_FONT_FALLBACK))
