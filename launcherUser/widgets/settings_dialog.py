import json
import os
import psutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt

from utils.base_dialog import BaseDialog


class SettingsDialog(BaseDialog):
    def __init__(self, settings_file=None, icon_path=None, parent=None):
        super().__init__(parent, icon_path=icon_path)
        self._settings_file = settings_file or os.path.join(".", "resources", "settings.json")
        self.setWindowTitle("Settings")
        self.setFixedSize(320, 150)

        self.available_ram_mb = psutil.virtual_memory().total // (1024 * 1024)

        # RAM choices in 1024MB steps
        self.ram_choices = list(range(1024, self.available_ram_mb + 1, 1024))
        if self.available_ram_mb not in self.ram_choices:
            self.ram_choices.append(self.available_ram_mb)

        self.load_settings()

        layout = QVBoxLayout()
        form = QFormLayout()

        # Min RAM
        self.min_ram_input = QComboBox()
        self.min_ram_input.setEditable(True)
        self.min_ram_input.addItems(str(r) for r in self.ram_choices)
        self.min_ram_input.setCurrentText(self.settings["ramMinimumMB"])
        form.addRow("Minimum RAM (MB):", self.min_ram_input)

        # Max RAM
        self.max_ram_input = QComboBox()
        self.max_ram_input.setEditable(True)
        self.max_ram_input.addItems(str(r) for r in self.ram_choices)
        self.max_ram_input.setCurrentText(self.settings["ramMaximumMB"])
        form.addRow("Maximum RAM (MB):", self.max_ram_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def load_settings(self):
        try:
            with open(self._settings_file, "r") as f:
                self.settings = json.load(f)
        except Exception:
            self.settings = {
                "ramMinimumMB": "2048",
                "ramMaximumMB": str(self.available_ram_mb)
            }

    def save_and_close(self):
        min_ram = self.min_ram_input.currentText()
        max_ram = self.max_ram_input.currentText()

        if not min_ram.isdigit() or not max_ram.isdigit():
            QMessageBox.warning(self, "Invalid Input",
                                "RAM values must be numeric.")
            return

        if int(min_ram) > int(max_ram):
            QMessageBox.warning(self, "Invalid Range",
                                "Minimum RAM must be less than Maximum RAM.")
            return

        self.settings["ramMinimumMB"] = min_ram
        self.settings["ramMaximumMB"] = max_ram

        with open(self._settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)

        self.accept()
