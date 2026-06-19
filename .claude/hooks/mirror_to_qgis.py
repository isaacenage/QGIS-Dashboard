#!/usr/bin/env python
"""PostToolUse hook: mirror edited plugin files into the installed QGIS plugin.

Whenever Edit/Write/MultiEdit touches a file under the plugin *source* root,
copy it (overwriting, creating it if new) to the installed-plugin location,
preserving the relative subpath. Reads the hook payload (JSON) on stdin.

Always exits 0 so a copy failure can never block the edit itself.
"""
import json
import shutil
import sys
from pathlib import Path

# Source = the repo's shippable plugin folder.
SRC_ROOT = Path(
    r"C:\Users\enage.isaac\Desktop\Codes\Tools\QGIS Plugins\plugins\qgis_dashboards"
)
# Destination = the plugin folder QGIS actually loads.
DST_ROOT = Path(
    r"C:\Users\enage.isaac\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\qgis_dashboards"
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return

    src = Path(file_path)
    try:
        # relative_to is case-insensitive on Windows paths; resolve() canonicalizes.
        rel = src.resolve().relative_to(SRC_ROOT.resolve())
    except (ValueError, OSError):
        return  # edited file lives outside the plugin source tree -> ignore

    if not src.is_file():
        return  # deleted/moved between edit and hook -> nothing to copy

    dst = DST_ROOT / rel
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as exc:
        # Note it for the user, but never fail the edit.
        print(json.dumps({"systemMessage": f"QGIS mirror skipped {rel}: {exc}"}))
        return

    print(json.dumps({"suppressOutput": True}))


if __name__ == "__main__":
    main()
