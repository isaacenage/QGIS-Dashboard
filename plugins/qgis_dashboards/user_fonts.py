# -*- coding: utf-8 -*-
"""User-supplied custom fonts.

Lets the user bring their own ``.ttf``/``.otf`` into the dashboard from
*Settings -> Themes*. Uploaded files are copied into a **per-profile** folder
(under the QGIS settings directory, NOT the project) and re-registered with Qt's
application font database on every plugin load, so a custom font is available in
**every** QGIS project and dashboard on that machine -- not just the active one.

This is the user-font analogue of :mod:`fonts` (which registers the bundled
Inter family). Like that module it is **resilient**: every operation is wrapped
so a missing/locked/invalid file degrades to the platform fallback stack rather
than breaking window creation or a project load.

Fonts also travel with the dashboard: :func:`embedded_payload` base64-encodes
the referenced custom files for embedding in a ``.qdash`` file and the HTML
export, and :func:`install_embedded` writes such embedded fonts back into the
local folder on open (so a shared dashboard installs its fonts too).
"""

import base64
import os
import shutil

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QFontDatabase

_SUFFIXES = (".ttf", ".otf")
_FORMATS = {".ttf": "truetype", ".otf": "opentype"}

# family name -> {"path": <abs path>, "id": <addApplicationFont id>}
_fonts = {}
# absolute paths already handed to addApplicationFont (dedupe re-registration)
_registered_paths = set()


def fonts_dir():
    """Absolute path to the per-profile custom-fonts folder (created on demand).

    Lives under the active QGIS profile (``.../profiles/<name>/qgis_dashboards/
    fonts``) so it survives plugin updates and is shared across every project.
    """
    base = QgsApplication.qgisSettingsDirPath()
    path = os.path.join(base, "qgis_dashboards", "fonts")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:                       # pragma: no cover - defensive
        pass
    return path


def _format_for(path):
    return _FORMATS.get(os.path.splitext(path)[1].lower(), "truetype")


def _register_file(path):
    """Register one font file with Qt; record the families it provides.

    Idempotent per path; returns the list of families newly registered (or the
    already-known ones for an already-registered path)."""
    abs_path = os.path.abspath(path)
    if abs_path in _registered_paths:
        return [f for f, info in _fonts.items() if info["path"] == abs_path]
    try:
        font_id = QFontDatabase.addApplicationFont(abs_path)
    except Exception:                     # pragma: no cover - defensive
        return []
    if font_id == -1:
        return []
    _registered_paths.add(abs_path)
    families = []
    for family in QFontDatabase.applicationFontFamilies(font_id):
        if family:
            _fonts[family] = {"path": abs_path, "id": font_id}
            families.append(family)
    return families


def register_all():
    """Register every font file in :func:`fonts_dir`. Returns family names.

    Safe to call repeatedly and at startup before any QSS / ``QFontComboBox`` is
    built, so user fonts appear in the pickers and render in tiles."""
    directory = fonts_dir()
    try:
        names = sorted(os.listdir(directory))
    except OSError:                       # pragma: no cover - defensive
        names = []
    for name in names:
        if name.lower().endswith(_SUFFIXES):
            _register_file(os.path.join(directory, name))
    return custom_families()


def _unique_dest(directory, filename):
    """A destination path in *directory* that does not clobber an existing file."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = "{}_{}{}".format(base, i, ext)
        i += 1
    return os.path.join(directory, candidate)


def add_font(src_path):
    """Copy a user-picked ``.ttf``/``.otf`` into the folder and register it.

    Returns the list of family names added (empty on any failure, so the caller
    can show a message bar without a try/except)."""
    try:
        if not src_path or not os.path.isfile(src_path):
            return []
        if not src_path.lower().endswith(_SUFFIXES):
            return []
        dest = _unique_dest(fonts_dir(), os.path.basename(src_path))
        shutil.copyfile(src_path, dest)
    except OSError:
        return []
    return _register_file(dest)


def remove_font(family):
    """Unregister *family* and delete its file. Returns True on success."""
    info = _fonts.get(family)
    if not info:
        return False
    ok = True
    try:
        QFontDatabase.removeApplicationFont(info["id"])
    except Exception:                     # pragma: no cover - defensive
        ok = False
    try:
        if os.path.exists(info["path"]):
            os.remove(info["path"])
    except OSError:
        ok = False
        return ok                         # keep the registry entry if locked
    _registered_paths.discard(info["path"])
    _fonts.pop(family, None)
    return ok


def custom_families():
    """Sorted family names currently installed as user fonts."""
    return sorted(_fonts.keys())


def path_for_family(family):
    """On-disk path for an installed custom *family*, or ``None``."""
    info = _fonts.get(family)
    return info["path"] if info else None


def embedded_payload(families):
    """Base64-encode the files for *families* that are installed custom fonts.

    Returns a list of ``{family, filename, format, data}`` dicts (skipping
    families with no installed file or an unreadable file) for embedding in a
    ``.qdash`` blob or the HTML export."""
    out = []
    for family in families or []:
        path = path_for_family(family)
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode("ascii")
        except OSError:                   # pragma: no cover - defensive
            continue
        out.append({
            "family": family,
            "filename": os.path.basename(path),
            "format": _format_for(path),
            "data": data,
        })
    return out


def install_embedded(entries):
    """Write embedded font *entries* into the folder and register them.

    Used when opening a ``.qdash`` that carries fonts: each entry is decoded and
    written (if a file of that name isn't already present), then registered, so
    the shared dashboard both renders and installs its fonts locally. Returns
    the family names installed."""
    installed = []
    directory = fonts_dir()
    for entry in entries or []:
        filename = (entry or {}).get("filename")
        data = (entry or {}).get("data")
        if not filename or not data:
            continue
        dest = os.path.join(directory, os.path.basename(filename))
        try:
            if not os.path.exists(dest):
                with open(dest, "wb") as fh:
                    fh.write(base64.b64decode(data))
        except (OSError, ValueError, TypeError):
            continue
        installed.extend(_register_file(dest))
    return installed
