# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
from qgis.PyQt.QtGui import QIcon


def _plugin_base_dir() -> str:
    """
    Returns the absolute path to the plugin root directory.
    Based on the current file location to avoid relying on CWD.
    """

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def svg_path(filename: str) -> str:
    """
    Build the absolute path for an SVG stored under resources/SVG.
    Returns an empty string when filename is falsy.
    """

    if not filename:
        return ""
    return os.path.join(_plugin_base_dir(), "resources", "SVG", filename)


def svg_icon(filename: str) -> QIcon:
    """
    Return a QIcon from an SVG in resources/SVG.
    Gracefully falls back to an empty icon when the file is missing.
    """

    path = svg_path(filename)
    if not path or not os.path.exists(path):
        return QIcon()
    return QIcon(path)


__all__ = ["svg_icon", "svg_path"]
