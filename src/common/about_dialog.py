# src/common/about_dialog.py — Shared About modal (user and admin launcher)

import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from src.common.about import get_about_html


class AboutDialog(QDialog):
    """Modal showing launcher version, credits (including main developer), and licenses."""

    def __init__(self, parent=None, launcher_name: str = "Matteino Launcher", icon_path=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setMinimumSize(480, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        if icon_path:
            icon_file = os.path.join(icon_path, "matteinocraft_mc_logo.png") if os.path.isdir(icon_path) else icon_path
            if os.path.isfile(icon_file):
                self.setWindowIcon(QIcon(icon_file))

        try:
            from launcherUser.utils.base_stylesheet import getBaseStylesheet
            self.setStyleSheet(getBaseStylesheet())
        except Exception:
            try:
                from utils.base_stylesheet import getBaseStylesheet
                self.setStyleSheet(getBaseStylesheet())
            except Exception:
                pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(get_about_html(launcher_name=launcher_name))
        self.browser.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.browser)
