# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

"""
Centralized color and typography definitions for the Summarizer plugin.

The palette follows modern analytics styling guidelines so the rest
of the codebase can import consistent tokens instead of hardcoding values.
"""

from collections import ChainMap

from .utils.fonts import ui_font_family, ui_font_stack

COLORS = {
    "color_app_bg": "#FAFAFA",
    "color_surface": "#FFFFFF",
    "color_border": "#E2E6EC",
    "color_text_primary": "#252B33",
    "color_text_secondary": "#55606D",
    "color_primary": "#5A3FE6",
    "color_primary_hover": "#4936C8",
    "color_brand": "#5A3FE6",
    "color_brand_soft": "rgba(104, 92, 208, 0.10)",
    "color_secondary": "#2B7DE9",
    "color_success": "#2FB26A",
    "color_warning": "#F2994A",
    "color_error": "#EB5757",
    "color_table_zebra": "#F6F8FB",
    "color_table_selection": "#E5E7EB",
    "color_splitter": "#E2E6EC",
    "color_shadow": "rgba(17, 24, 39, 0.06)",
}

DARK_COLORS = {
    "color_app_bg": "#0B1020",
    "color_surface": "#0B1020",
    "color_border": "#334155",
    "color_text_primary": "#F8FAFC",
    "color_text_secondary": "#CBD5E1",
    "color_primary": "#7C6CFF",
    "color_primary_hover": "#6A5AE8",
    "color_brand": "#8B7CFF",
    "color_brand_soft": "rgba(139, 124, 255, 0.20)",
    "color_secondary": "#60A5FA",
    "color_success": "#4ADE80",
    "color_warning": "#FDBA74",
    "color_error": "#F87171",
    "color_table_zebra": "#182230",
    "color_table_selection": "#374151",
    "color_splitter": "#374151",
    "color_shadow": "rgba(0, 0, 0, 0.30)",
}

TYPOGRAPHY = {
    "font_family": ui_font_family(),
    "font_ui_stack": ui_font_stack(),
    "font_mono_stack": '"Cascadia Mono", "SF Mono", Consolas, "Liberation Mono", monospace',
    "font_base_size": 11,
    "font_title_size": 18,
    "font_subtitle_size": 14,
    "font_section_size": 13,
    "font_body_size": 11,
    "font_small_size": 10,
    "font_page_title_px": 24,
    "font_section_title_px": 16,
    "font_body_px": 13,
    "font_secondary_px": 12,
    "font_caption_px": 11,
    "font_button_px": 13,
    "font_chip_px": 12,
    "font_weight_regular": 400,
    "font_weight_medium": 500,
    "font_weight_semibold": 600,
}

MISC = {
    "radius_surface": 12,
    "radius_button": 10,
    "radius_input": 8,
    "radius_table": 10,
    "button_height": 36,
    "input_height": 32,
    "tab_height": 36,
}


def palette_context(theme_mode: str = "light"):
    """
    Helper that merges all dictionaries so template formatting can use
    the keys as `${color_app_bg}`, `${font_title_size}`, etc.
    """

    mode = str(theme_mode or "light").strip().lower()
    colors = DARK_COLORS if mode == "dark" else COLORS
    return ChainMap({}, colors, TYPOGRAPHY, MISC)
