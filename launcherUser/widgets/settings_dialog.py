import json
import os
import sys
import psutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QHBoxLayout, QLineEdit, QFileDialog,
    QWidget, QTabWidget, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt
from utils.base_dialog import BaseDialog

# Suggested JVM arguments for modded Minecraft (Java 17+). G1GC tuning can reduce stutters.
SUGGESTED_JVM_ARGS = (
    "-XX:+UnlockExperimentalVMOptions -XX:+UseG1GC "
    "-XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 "
    "-XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M"
)


class SettingsDialog(BaseDialog):
    def __init__(
        self,
        settings_file=None,
        icon_path=None,
        config=None,
        save_minecraft_callback=None,
        save_translations_and_restart_callback=None,
        parent=None,
    ):
        super().__init__(parent, icon_path=icon_path)
        config = config or {}
        self._settings_file = settings_file or os.path.join(".", "resources", "settings.json")
        self._config_minecraft = config.get("minecraft", {})
        self._config_general = config.get("general", {})
        self._config_server_status = config.get("server_status", {})
        self._save_config_callback = save_minecraft_callback  # receives full override dict
        self._save_translations_and_restart = save_translations_and_restart_callback
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumSize(440, 320)

        self.available_ram_mb = psutil.virtual_memory().total // (1024 * 1024)
        self.ram_choices = list(range(1024, min(self.available_ram_mb + 1, 32768), 1024))
        if self.available_ram_mb not in self.ram_choices and self.available_ram_mb < 32768:
            self.ram_choices.append(self.available_ram_mb)
        if not self.ram_choices:
            self.ram_choices = [2048, 4096, 8192]

        layout = QVBoxLayout()
        tabs = QTabWidget()

        # --- Tab: General ---
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        general_layout.addWidget(QLabel(self.tr("Language:")))
        self._language_combo = QComboBox()
        self._language_choices = []
        if self._save_translations_and_restart:
            from src.common import translations as common_translations
            self._language_choices = common_translations.get_available_languages("user")
            current_file = common_translations.get_current_translation_file(config)
            self._language_combo.blockSignals(True)
            for i, choice in enumerate(self._language_choices):
                self._language_combo.addItem(choice["name"], choice)
                if (choice.get("file") or "") == current_file:
                    self._language_combo.setCurrentIndex(i)
            self._language_combo.blockSignals(False)
            self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        else:
            self._language_combo.addItem("English", {"id": "", "file": ""})
            self._language_combo.setEnabled(False)
        general_layout.addWidget(self._language_combo)

        general_layout.addSpacing(20)
        self._server_status_check = QCheckBox(self.tr("Show server status panel"))
        self._server_status_check.setChecked(bool(self._config_server_status.get("enabled", False)))
        self._server_status_check.setToolTip(self.tr("Display server list and online status in the launcher. Servers are configured in the launcher config."))
        general_layout.addWidget(self._server_status_check)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(15, 300)
        self._refresh_spin.setSuffix(" " + self.tr("seconds"))
        self._refresh_spin.setValue(max(15, min(300, int(self._config_server_status.get("refresh_interval_seconds", 60)))))
        general_layout.addWidget(QLabel(self.tr("Refresh server status every:")))
        general_layout.addWidget(self._refresh_spin)

        general_layout.addSpacing(12)
        self._close_on_play_check = QCheckBox(self.tr("Close launcher when game starts"))
        self._close_on_play_check.setChecked(self._config_general.get("close_launcher_on_play", True))
        self._close_on_play_check.setToolTip(self.tr("Hide the launcher window when Minecraft is launched. Uncheck to keep it open."))
        general_layout.addWidget(self._close_on_play_check)

        general_layout.addStretch()
        tabs.addTab(general_tab, self.tr("General"))

        # --- Tab: RAM ---
        ram_tab = QWidget()
        ram_form = QFormLayout(ram_tab)
        min_ram = self._config_minecraft.get("min_ram_mb") or self._load_ram_from_settings("ramMinimumMB", 2048)
        max_ram = self._config_minecraft.get("max_ram_mb") or self._load_ram_from_settings("ramMaximumMB", 4096)

        self.min_ram_input = QComboBox()
        self.min_ram_input.setEditable(True)
        self.min_ram_input.addItems(str(r) for r in self.ram_choices)
        self.min_ram_input.setCurrentText(str(min_ram))
        ram_form.addRow(self.tr("Min RAM (MB):"), self.min_ram_input)

        self.max_ram_input = QComboBox()
        self.max_ram_input.setEditable(True)
        self.max_ram_input.addItems(str(r) for r in self.ram_choices)
        self.max_ram_input.setCurrentText(str(max_ram))
        ram_form.addRow(self.tr("Max RAM (MB):"), self.max_ram_input)
        tabs.addTab(ram_tab, self.tr("RAM"))

        # --- Tab: Java settings ---
        java_tab = QWidget()
        java_layout = QVBoxLayout(java_tab)

        java_layout.addWidget(QLabel(self.tr("Java path:")))
        java_row = QHBoxLayout()
        self.java_path_input = QLineEdit()
        self.java_path_input.setPlaceholderText(self.tr("Leave empty to use auto-detected Java"))
        self.java_path_input.setText(self._config_minecraft.get("java_path") or "")
        java_row.addWidget(self.java_path_input)
        browse_btn = QPushButton(self.tr("Browse…"))
        browse_btn.clicked.connect(self._browse_java)
        java_row.addWidget(browse_btn)
        java_layout.addLayout(java_row)

        java_layout.addWidget(QLabel(self.tr("Custom JVM arguments:")))
        jvm_hint = QLabel(
            self.tr("Extra flags for Java (e.g. G1GC for modded). -Xms/-Xmx are set from RAM above.")
        )
        jvm_hint.setWordWrap(True)
        jvm_hint.setStyleSheet("color: #888; font-size: 9pt;")
        java_layout.addWidget(jvm_hint)
        self.jvm_args_input = QPlainTextEdit()
        self.jvm_args_input.setPlaceholderText(self.tr("e.g. -XX:+UseG1GC -XX:MaxGCPauseMillis=50 …"))
        self.jvm_args_input.setMaximumHeight(72)
        self.jvm_args_input.setPlainText(self._config_minecraft.get("jvm_args") or "")
        java_layout.addWidget(self.jvm_args_input)
        suggest_btn = QPushButton(self.tr("Use suggested (G1GC for modded)"))
        suggest_btn.clicked.connect(self._fill_suggested_jvm_args)
        java_layout.addWidget(suggest_btn)

        tabs.addTab(java_tab, self.tr("Java settings"))

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _on_language_changed(self, index: int):
        if index < 0 or index >= len(self._language_choices) or not self._save_translations_and_restart:
            return
        choice = self._language_choices[index]
        if choice["id"] == "":
            trans = {"enabled": False, "file": "", "locale": "en"}
        else:
            trans = {"enabled": True, "file": choice["file"], "locale": choice["id"]}
        self._save_translations_and_restart(trans)

    def _browse_java(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Java executable"),
            os.path.dirname(self.java_path_input.text()) or os.path.expanduser("~"),
            self.tr("Executables (*.exe);;All files (*)") if os.name == "nt" else self.tr("All files (*)"),
        )
        if path:
            self.java_path_input.setText(path)

    def _load_ram_from_settings(self, key, default):
        try:
            with open(self._settings_file, "r") as f:
                data = json.load(f)
            return int(data.get(key, default))
        except Exception:
            return default

    def _fill_suggested_jvm_args(self):
        self.jvm_args_input.setPlainText(SUGGESTED_JVM_ARGS)

    def save_and_close(self):
        min_ram = self.min_ram_input.currentText().strip()
        max_ram = self.max_ram_input.currentText().strip()
        jvm_args = self.jvm_args_input.toPlainText().strip()
        java_path = self.java_path_input.text().strip()

        if not min_ram.isdigit() or not max_ram.isdigit():
            QMessageBox.warning(self, self.tr("Invalid Input"), self.tr("RAM values must be numeric."))
            return
        if int(min_ram) > int(max_ram):
            QMessageBox.warning(self, self.tr("Invalid Range"), self.tr("Min RAM must be ≤ Max RAM."))
            return

        override = {
            "minecraft": {
                "min_ram_mb": int(min_ram),
                "max_ram_mb": int(max_ram),
                "jvm_args": jvm_args,
                "java_path": java_path,
            },
            "general": {
                "close_launcher_on_play": self._close_on_play_check.isChecked(),
            },
            "server_status": {
                "enabled": self._server_status_check.isChecked(),
                "refresh_interval_seconds": self._refresh_spin.value(),
            },
        }

        if self._save_config_callback:
            self._save_config_callback(override)
        else:
            try:
                os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
                with open(self._settings_file, "w") as f:
                    json.dump(
                        {"ramMinimumMB": int(min_ram), "ramMaximumMB": int(max_ram)},
                        f, indent=4,
                    )
            except Exception:
                pass

        self.accept()
