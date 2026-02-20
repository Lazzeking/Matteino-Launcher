# windows/workspace_selection_window.py

import os
import sys
import json

from src.common import paths as common_paths

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QFileDialog, QMessageBox, QLabel, QComboBox
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QSize, Qt

from src.common.version import __version__ as LAUNCHER_VERSION
from src.common.about_dialog import AboutDialog
from src.common import config as common_config
from src.common import translations as common_translations
from windows.workspace_window import WorkspaceWindow


class WorkspaceSelectionWindow(QMainWindow):
    def __init__(self, config=None, paths=None):
        super().__init__()
        self.config = config or {}
        self.paths = paths or {}
        self._workspaces_file = self.paths.get("workspaces_file", os.path.join(os.getcwd(), "resources", "workspaces.json"))
        images_dir = self.paths.get("images_dir", "")
        if getattr(sys, "frozen", False):
            project_root = common_paths.writable_dir()
        else:
            project_root = os.path.dirname(os.path.dirname(images_dir)) if images_dir else os.getcwd()

        # Resolve icon and logo from config
        icon_key = self.config.get("icon_path", "launcherAdmin/resources/images/icon.png")
        logo_key = self.config.get("logo_path", "launcherAdmin/resources/images/logo.png")
        if icon_key and not os.path.isabs(icon_key):
            icon_candidate = os.path.join(project_root, icon_key)
            self._icon_file = icon_candidate if os.path.isfile(icon_candidate) else (os.path.join(images_dir, "matteinocraft_mc_logo.png") if images_dir else None)
        else:
            self._icon_file = icon_key if icon_key and os.path.isfile(icon_key) else (os.path.join(images_dir, "matteinocraft_mc_logo.png") if images_dir else None)
        if logo_key and not os.path.isabs(logo_key):
            logo_candidate = os.path.join(project_root, logo_key)
            self._logo_path = logo_candidate if os.path.isfile(logo_candidate) else (os.path.join(images_dir, "matteinocraft_mc_logo.png") if images_dir else None)
        else:
            self._logo_path = logo_key if logo_key and os.path.isfile(logo_key) else (os.path.join(images_dir, "matteinocraft_mc_logo.png") if images_dir else None)

        if self._icon_file and os.path.isfile(self._icon_file):
            self.setWindowIcon(QIcon(self._icon_file))
        self.setWindowTitle(self.tr(self.config.get("window_title", "Matteino Launcher - Admin - Select workspace")))
        self.setMinimumSize(600, 400)

        self.workspaces = self.load_workspaces()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.left_panel = QVBoxLayout()
        self.right_panel = QVBoxLayout()

        self.layout.addLayout(self.left_panel, 1)
        self.layout.addLayout(self.right_panel, 3)

        self.setup_ui()

    def setup_ui(self):
        # Load the logo
        logo_path = self._logo_path or "./resources/images/matteinocraft_mc_logo.png"
        pixmap = QPixmap(logo_path)

        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaledToWidth(200)  # Scale width as needed
            logo_label = QLabel()
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.left_panel.addWidget(logo_label)
        else:
            fallback_label = QLabel(self.tr("Logo not found"))
            fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.left_panel.addWidget(fallback_label)

        self.left_panel.addSpacing(30)

        # Add/Remove buttons
        btn_add = QPushButton(self.tr("Add workspace"))
        btn_add.clicked.connect(self.add_workspace)
        self.left_panel.addWidget(btn_add)

        self.btn_remove = QPushButton(self.tr("Remove workspace"))
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self.remove_workspace)
        self.left_panel.addWidget(self.btn_remove)

        # Language selector
        self.left_panel.addWidget(QLabel(self.tr("Language:")))
        self.language_combo = QComboBox()
        self._language_choices = common_translations.get_available_languages("admin")
        current_file = common_translations.get_current_translation_file(self.config)
        self.language_combo.blockSignals(True)
        for i, choice in enumerate(self._language_choices):
            self.language_combo.addItem(choice["name"], choice)
            if choice["file"] == current_file:
                self.language_combo.setCurrentIndex(i)
        self.language_combo.blockSignals(False)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.left_panel.addWidget(self.language_combo)

        # Launcher version (click to open About / credits and licenses)
        version_btn = QPushButton(self.tr("Launcher v{0}").format(LAUNCHER_VERSION))
        version_btn.setFlat(True)
        version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        version_btn.setStyleSheet("color: #fff; border: none; background: none;")
        version_btn.clicked.connect(self.show_about)
        self.left_panel.addWidget(version_btn)

        # List of workspaces
        self.workspace_list = QListWidget()
        self.workspace_list.addItems(
            [os.path.basename(w) for w in self.workspaces])
        self.workspace_list.itemSelectionChanged.connect(
            self.on_selection_change)
        self.workspace_list.itemDoubleClicked.connect(self.open_workspace)
        self.right_panel.addWidget(self.workspace_list)

    def load_workspaces(self):
        if not self._workspaces_file or not os.path.exists(self._workspaces_file):
            return []

        with open(self._workspaces_file, "r") as f:
            data = json.load(f)
            return data.get("workspaces", [])

    def save_workspaces(self):
        if self._workspaces_file:
            os.makedirs(os.path.dirname(self._workspaces_file), exist_ok=True)
            with open(self._workspaces_file, "w") as f:
                json.dump({"workspaces": self.workspaces}, f, indent=2)

    def add_workspace(self):
        path = QFileDialog.getExistingDirectory(
            self, self.tr("Select a folder"))
        if not path:
            return

        if path in self.workspaces:
            QMessageBox.warning(self, self.tr("Error"),
                                self.tr("Workspace already exists"))
            return

        self.workspaces.append(path)
        self.save_workspaces()
        self.workspace_list.addItem(os.path.basename(path))

    def remove_workspace(self):
        selected = self.workspace_list.currentRow()
        if selected < 0:
            return

        del self.workspaces[selected]
        self.workspace_list.takeItem(selected)
        self.save_workspaces()
        self.btn_remove.setEnabled(False)

    def on_selection_change(self):
        self.btn_remove.setEnabled(self.workspace_list.currentRow() >= 0)

    def _on_language_changed(self, index: int):
        if index < 0 or index >= len(self._language_choices):
            return
        choice = self._language_choices[index]
        if choice["id"] == "":
            trans = {"enabled": False, "file": "", "locale": "en"}
        else:
            trans = {"enabled": True, "file": choice["file"], "locale": choice["id"]}
        common_config.save_user_config("admin", {"translations": trans})
        # Restart so the new translator is loaded
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def show_about(self):
        dialog = AboutDialog(
            parent=self,
            launcher_name=self.tr("Matteino Launcher Admin"),
            icon_path=self._icon_file,
        )
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.exec()

    def open_workspace(self):
        index = self.workspace_list.currentRow()
        if index < 0:
            return

        workspace_path = self.workspaces[index]
        self.workspace_window = WorkspaceWindow(workspace_path, icon_path=self._icon_file, config=self.config)
        self.workspace_window.show()
        self.close()
