# -*- coding: utf-8 -*-
"""The *Publish to public* dialog.

Collects the GitHub token + target repo (persisted in ``QSettings``), runs the
large-data guard, then publishes the current dashboard via :mod:`publisher`
behind a modal progress dialog and shows the resulting public URL.

Security note surfaced in the UI: the token is stored locally (on Windows that's
the user's registry) in plain text, so we recommend a *fine-grained* token
scoped to only the gallery repo with *Contents: read and write*.
"""

from qgis.PyQt.QtCore import Qt, QSettings, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QDialogButtonBox,
    QMessageBox, QProgressDialog, QApplication,
)

from .github_publish import DEFAULT_REPO, DEFAULT_BRANCH, parse_repo
from .github_client import PublishError
from .publisher import publish_dashboard, oversize_referenced_layers

SCOPE = "qgis_dashboards/publish"


class PublishDialog(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self.setWindowTitle("Publish to public")
        self.setMinimumWidth(460)

        settings = QSettings()
        token = settings.value(SCOPE + "/token", "", type=str)
        repo = settings.value(SCOPE + "/repo", DEFAULT_REPO, type=str)
        branch = settings.value(SCOPE + "/branch", DEFAULT_BRANCH, type=str)
        author = settings.value(SCOPE + "/author", "", type=str)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        intro = QLabel(
            "Publish this dashboard to the public gallery. The plugin exports "
            "the interactive HTML, renders a thumbnail and commits both to your "
            "gallery repository in one step.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._token_edit = QLineEdit(token)
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("github_pat_…")
        form.addRow("GitHub token", self._token_edit)

        self._repo_edit = QLineEdit(repo)
        self._repo_edit.setPlaceholderText(DEFAULT_REPO)
        form.addRow("Repository", self._repo_edit)

        self._branch_edit = QLineEdit(branch)
        self._branch_edit.setPlaceholderText(DEFAULT_BRANCH)
        form.addRow("Branch", self._branch_edit)

        self._author_edit = QLineEdit(author)
        self._author_edit.setPlaceholderText("Your name (shown on the card)")
        form.addRow("Author", self._author_edit)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional one-line summary")
        form.addRow("Description", self._desc_edit)
        root.addLayout(form)

        hint = QLabel(
            "Use a <b>fine-grained</b> token scoped to only this repository with "
            "<b>Contents: read and write</b>. It's stored locally on this "
            "computer in plain text — never share your QGIS profile with it.")
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#55606d; font-size:11px;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel)
        self._publish_btn = buttons.addButton(
            "Publish", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        self._publish_btn.clicked.connect(self._publish)
        root.addWidget(buttons)

    # ---- actions --------------------------------------------------------

    def _publish(self):
        token = self._token_edit.text().strip()
        repo = self._repo_edit.text().strip() or DEFAULT_REPO
        branch = self._branch_edit.text().strip() or DEFAULT_BRANCH
        author = self._author_edit.text().strip()
        description = self._desc_edit.text().strip() or None

        if not token:
            QMessageBox.warning(
                self, "Token needed",
                "Paste a GitHub token to publish. Create a fine-grained token "
                "scoped to your gallery repository with Contents: read and "
                "write.")
            return
        try:
            parse_repo(repo)
        except ValueError as exc:
            QMessageBox.warning(self, "Check the repository", str(exc))
            return

        skip_layers = self._resolve_large_data()
        if skip_layers is False:        # user cancelled at the guard
            return

        # persist settings (token included — see the in-dialog warning)
        settings = QSettings()
        settings.setValue(SCOPE + "/token", token)
        settings.setValue(SCOPE + "/repo", repo)
        settings.setValue(SCOPE + "/branch", branch)
        settings.setValue(SCOPE + "/author", author)

        progress = QProgressDialog("Publishing…", None, 0, 100, self)
        progress.setWindowTitle("Publish to public")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setCancelButton(None)
        progress.setValue(0)

        def on_progress(step, frac):
            progress.setLabelText(step)
            progress.setValue(int(frac * 100))
            QApplication.processEvents()

        try:
            result = publish_dashboard(
                self._window, token, repo, branch, author,
                description=description, skip_layers=skip_layers,
                progress=on_progress)
        except PublishError as exc:
            progress.close()
            QMessageBox.critical(self, "Publish failed", str(exc))
            return
        except Exception as exc:        # never half-report a silent failure
            progress.close()
            QMessageBox.critical(
                self, "Publish failed",
                "Something went wrong while publishing:\n{}".format(exc))
            return
        finally:
            progress.close()

        self._show_success(result)
        self.accept()

    def _resolve_large_data(self):
        """Return a set of layer ids to skip, an empty set, or ``False`` to cancel."""
        big = oversize_referenced_layers(self._window)
        if not big:
            return set()
        lines = ["These bound layers are large to embed in a single HTML file:\n"]
        for _lid, name, count, est in big:
            lines.append("  • {}: {:,} features (~{:.0f} MB)".format(
                name, count, est / (1024.0 * 1024.0)))
        lines.append("\nPublishing them may make the dashboard slow to open.")
        box = QMessageBox(self)
        box.setWindowTitle("Large data")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("\n".join(lines))
        proceed = box.addButton("Publish anyway", QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton("Skip these layers", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is skip:
            return {lid for lid, _n, _c, _e in big}
        return set()

    def _show_success(self, result):
        url = result["url"]
        verb = "updated" if result["is_update"] else "published"
        box = QMessageBox(self)
        box.setWindowTitle("Published")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Your dashboard was {}.\n\nIt will be live within a minute "
                    "at:\n{}".format(verb, url))
        open_btn = box.addButton("Open in browser", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(url))
