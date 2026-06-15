"""Local test runner for a QGIS python env.

The plugin modules use package-relative imports (``from .theme import Theme``),
but the test files import them by bare name (``from bus import ...``). To bridge
that, this runner imports the real package submodules and aliases them under
their bare names in ``sys.modules`` before loading the tests.

Usage (inside a QGIS python env):
    python _run_tests.py test_multipage test_dashboard
"""
import os
import sys
import importlib
import unittest

here = os.path.dirname(os.path.abspath(__file__))   # .../qgis_dashboard/test
plugin = os.path.dirname(here)                       # .../qgis_dashboard
root = os.path.dirname(plugin)                       # repo root
pkg = os.path.basename(plugin)                       # "qgis_dashboard"

for p in (root, here):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import package submodules and expose them under bare names for the tests.
_BARE = (
    "theme", "bus", "dashboard_canvas", "page_view", "window", "elements",
    "add_element_dialog", "settings_dialog", "appearance_dialog",
    "connections_dialog",
)
for mod in _BARE:
    sys.modules[mod] = importlib.import_module("{}.{}".format(pkg, mod))

# Importing the ``elements`` package above also imported its submodules under
# their real ``<pkg>.elements.*`` names. Alias them under the bare dotted names
# the tests use (``from elements.charts.painters import ...``) so they resolve
# to the already-imported modules instead of being re-executed (which would
# break their package-relative imports).
for sub in ("base", "chart", "chart_specs", "charts", "charts.painters",
            "pivot", "pivot_engine",
            "indicator", "list_element", "map_element", "category_selector"):
    full = "{}.elements.{}".format(pkg, sub)
    if full in sys.modules:
        sys.modules["elements.{}".format(sub)] = sys.modules[full]

# Bootstrap a real QGIS/Qt application so widget-level tests can build QWidgets.
# (The bundled test/qgis_interface.py stub is a stale QGIS-2 scaffold that fails
# to import on QGIS 3, so utilities.get_qgis_app() returns None — we don't rely
# on it here.)
from qgis.core import QgsApplication  # noqa: E402
if QgsApplication.instance() is None:
    _QGIS_APP = QgsApplication([b""], True)
    _QGIS_APP.initQgis()

names = sys.argv[1:] or ["test_multipage"]
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for name in names:
    suite.addTests(loader.loadTestsFromName(name))

result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
