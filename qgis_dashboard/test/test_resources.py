# coding=utf-8
"""Resources test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-15'
__copyright__ = 'Copyright 2026, Isaac Enage'

import os
import unittest

from qgis.PyQt.QtGui import QIcon


class qgisdashboardResourcesTest(unittest.TestCase):
    """Test the plugin icon loads.

    The plugin loads its icon from the filesystem when a compiled
    ``resources.py`` is absent, so we assert the on-disk icon is usable.
    """

    def test_icon_file_exists(self):
        """The icon.png shipped with the plugin exists."""
        icon_path = os.path.join(
            os.path.dirname(__file__), os.pardir, 'icon.png')
        self.assertTrue(os.path.exists(icon_path))

    def test_icon_loads(self):
        """The on-disk icon loads into a non-null QIcon."""
        icon_path = os.path.join(
            os.path.dirname(__file__), os.pardir, 'icon.png')
        icon = QIcon(icon_path)
        self.assertFalse(icon.isNull())


if __name__ == "__main__":
    suite = unittest.makeSuite(qgisdashboardResourcesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
