# -*- coding: utf-8 -*-
"""Grid settings dialog.

Lets the user set how many columns and rows the snap grid has. More cells =
finer placement and smaller default tiles; fewer cells = coarser, bigger tiles.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QSpinBox, QLabel, QDialogButtonBox
)


class GridSettingsDialog(QDialog):
    def __init__(self, cols, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard grid settings")
        form = QFormLayout(self)

        form.addRow(QLabel("The dashboard snaps tiles to an invisible grid.\n"
                           "Adjust its resolution below."))

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 48)
        self.cols_spin.setValue(int(cols))
        form.addRow("Columns (horizontal)", self.cols_spin)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 48)
        self.rows_spin.setValue(int(rows))
        form.addRow("Rows (vertical)", self.rows_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_grid(self):
        return self.cols_spin.value(), self.rows_spin.value()
