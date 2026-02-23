# windows/main_window.py

import base64
import html
import hashlib
import os
import sys
import json
import base64
import random
import subprocess
import threading
from urllib.parse import urljoin
import requests
import webbrowser
import minecraft_launcher_lib
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QComboBox, QGridLayout
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize, QTimer

from widgets.account_selector import AccountSelectorDialog
from src.common.about_dialog import AboutDialog
from widgets.settings_dialog import SettingsDialog
from auth.server import start_temp_server
from widgets.log_window import LogWindow
from workers.update_worker import UpdateModpackWorker
from workers.install_worker import MCModLoaderInstallerWorker
from widgets.optional_feature_selector import OptionalFeatureSelectorDialog
from src.common.version import __version__ as LAUNCHER_VERSION
from src.common import paths as common_paths
from src.common import config as common_config
from utils.base_stylesheet import getBaseStylesheet, set_images_dir
from workers.player_render_worker import PlayerRenderWorker
from workers.bust_render_worker import BustRenderWorker
from workers.server_status_worker import ServerStatusWorker
from utils.servers_dat import merge_config_servers


class UserLauncher(QMainWindow):
    login_success_signal = pyqtSignal(dict)  # Signal that sends login_data

    def __init__(self, config=None, paths=None, player_name="Notch"):
        super().__init__()
        self.login_success_signal.connect(self.handle_login_success)

        self.config = config or {}
        self.paths = paths or {}
        self.player_name = player_name
        self.current_login_url = None  # Store current login URL

        # Paths from common config (absolute when from get_user_paths)
        self._accounts_file = self.paths.get("accounts_file", "")
        self._packages_file = self.paths.get("packages_file", "")
        self._packs_dir = self.paths.get("packs_dir", "")
        images_dir = self.paths.get("images_dir", "")

        def _asset(cfg_key, default_rel, fallback_name):
            val = self.config.get(cfg_key, default_rel)
            if not val:
                return os.path.join(images_dir, fallback_name) if images_dir else None
            if os.path.isabs(val):
                return val if os.path.isfile(val) else (os.path.join(images_dir, fallback_name) if images_dir else None)
            # Relative paths: resolved relative to exe when frozen, else project root
            candidate = common_paths.resolve_asset_path(val)
            return candidate if os.path.isfile(candidate) else (os.path.join(images_dir, fallback_name) if images_dir else None)

        self._logo_path = _asset("logo_path", "launcherUser/resources/images/logo.png", "matteinocraft_logo.png") or ""
        self._icon_file = _asset("icon_path", "launcherUser/resources/images/icon.png", "matteinocraft_mc_logo.png")
        self._loading_path = _asset("loading_image_path", "launcherUser/resources/images/loading.png", "loading.png")
        self._icon_path = images_dir  # for dialogs

        window_title = self.config.get("window_title", "Matteino Launcher")
        self.setWindowTitle(window_title)
        self.setMinimumSize(700, 400)
        if self._icon_file and os.path.isfile(self._icon_file):
            self.setWindowIcon(QIcon(self._icon_file))
        # So combo down-arrow image (down_chevron.png) is found from any cwd
        set_images_dir(self._icon_path)
        self.setup_ui()

    def apply_material_theme(self):
        self.setStyleSheet(getBaseStylesheet())

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # === HEADER ===
        header = QHBoxLayout()
        header.setContentsMargins(10, 10, 10, 0)

        # === LEFT: Logo ===
        logo_container = QVBoxLayout()
        logo_container.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.logo_label = QLabel()
        logo_pixmap = QPixmap(self._logo_path) if self._logo_path and os.path.isfile(self._logo_path) else QPixmap()
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaledToWidth(
                300, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        logo_container.addWidget(self.logo_label)

        header.addLayout(logo_container)
        header.addStretch()

        # === RIGHT: User Info ===
        right_container = QVBoxLayout()
        right_container.setSpacing(8)
        right_container.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.account_data = None
        accounts = {}

        if self._accounts_file and os.path.isfile(self._accounts_file):
            with open(self._accounts_file, "r") as f:
                try:
                    accounts = json.load(f)
                    selected_uuid = accounts.get("selected")
                    self.account_data = accounts["accounts"].get(selected_uuid)
                except Exception as e:
                    print("Failed to load account:", e)

        self.player_render_button = QPushButton()
        self.player_render_button.setFlat(True)
        self.player_render_button.setIconSize(
            QSize(300, 300))
        self.player_render_button.setFixedSize(QSize(300, 300))
        self.player_render_button.setStyleSheet(
            "border: none; background: none;")
        self.player_render_button.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self.player_render_button.clicked.connect(
            self.change_player_render)

        if self.account_data:
            self.player_name = self.account_data["name"]
            # Change account button
            self.change_account_button = QPushButton(self.tr("Change Account"))
            self.change_account_button.clicked.connect(
                self.show_account_chooser)

            # Username
            name = self.account_data["name"]
            self.username_label = QLabel(name)
            self.username_label.setStyleSheet(
                "color: white; font-weight: bold; font-size: 14pt")
            self.username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Bust

            self.bust_label = QLabel()
            self.bust_label.setFixedSize(64, 64)
            self.load_bust(name, selected_uuid, accounts)

            self.change_player_render()

            # Add to container
            right_container.addWidget(
                self.bust_label, alignment=Qt.AlignmentFlag.AlignCenter)
            right_container.addWidget(self.username_label)
            right_container.addWidget(
                self.change_account_button, alignment=Qt.AlignmentFlag.AlignCenter)

        else:
            self.login_button = QPushButton(self.tr("Login with Microsoft"))
            self.login_button.clicked.connect(self.open_auth_browser)
            right_container.addWidget(
                self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)

            self.reopen_button = QPushButton(self.tr("Reopen Login Page"))
            self.reopen_button.clicked.connect(self.reopen_auth_browser)
            self.reopen_button.setVisible(False)  # Hidden by default
            right_container.addWidget(
                self.reopen_button, alignment=Qt.AlignmentFlag.AlignCenter)

        right_widget = QWidget()
        right_widget.setLayout(right_container)
        header.addWidget(right_widget)

        # Add header to main layout
        main_layout.addLayout(header)

        # === MAIN CONTENT: same row = player render (left) | stretch | server status (right, against window border) ===
        center = QHBoxLayout()
        center.setContentsMargins(10, 10, 10, 0)
        center.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        center.addWidget(self.player_render_button)

        # Server status table: built here, added on the right of this row (against right border)
        self.server_status_widget = None
        self.server_status_rows = []
        self.server_status_timer = None
        server_status_cfg = self.config.get("server_status") or {}
        if server_status_cfg.get("enabled") and server_status_cfg.get("servers"):
            servers = server_status_cfg["servers"]
            interval_sec = max(15, int(server_status_cfg.get("refresh_interval_seconds", 60)))
            default_icon = self._make_default_server_icon(32, 32, online=True)
            offline_icon = self._make_default_server_icon(32, 32, online=False)
            self._server_status_default_icon = default_icon
            self._server_status_offline_icon = offline_icon
            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setContentsMargins(18, 18, 18, 18)
            grid.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            cell_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            # Title: spans all columns, centered, with clear padding
            title = QLabel(self.tr("Server status"))
            title.setStyleSheet(
                "background: transparent; border: none; "
                "color: #aaa; font-size: 12px; font-weight: bold; "
                "padding: 8px 0 12px 0; margin: 0; "
                "border-bottom: 1px solid #444;"
            )
            title.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(title, 0, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            # Header row: plain text, one visual row (no per-cell boxes)
            header_style = (
                "background: transparent; border: none; "
                "color: #888; font-size: 11px; font-weight: bold; padding: 2px 0;"
            )
            grid.addWidget(QLabel(""), 1, 0)
            grid.addWidget(self._styled_label(self.tr("Name"), header_style, cell_align), 1, 1, alignment=cell_align)
            grid.addWidget(self._styled_label(self.tr("Status"), header_style, cell_align), 1, 2, alignment=cell_align)
            grid.addWidget(self._styled_label(self.tr("Players"), header_style, cell_align), 1, 3, alignment=cell_align)
            row_style = (
                "background: transparent; border: none; "
                "color: #ccc; font-size: 12px; padding: 5px 0;"
            )
            for row_idx, _ in enumerate(servers):
                icon_lbl = QLabel()
                icon_lbl.setFixedSize(32, 32)
                icon_lbl.setScaledContents(True)
                icon_lbl.setPixmap(offline_icon)
                icon_lbl.setStyleSheet("background: transparent; border: none;")
                name_lbl = QLabel(self.tr("—"))
                name_lbl.setStyleSheet(row_style)
                name_lbl.setAlignment(cell_align)
                status_lbl = QLabel(self.tr("—"))
                status_lbl.setStyleSheet(row_style)
                status_lbl.setAlignment(cell_align)
                players_lbl = QLabel(self.tr("—"))
                players_lbl.setStyleSheet(row_style)
                players_lbl.setAlignment(cell_align)
                grid.addWidget(icon_lbl, row_idx + 2, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(name_lbl, row_idx + 2, 1, alignment=cell_align)
                grid.addWidget(status_lbl, row_idx + 2, 2, alignment=cell_align)
                grid.addWidget(players_lbl, row_idx + 2, 3, alignment=cell_align)
                self.server_status_rows.append((icon_lbl, name_lbl, status_lbl, players_lbl))
            # Panel: single card with table inside (no stretch – table at top with padding)
            self.server_status_widget = QWidget()
            self.server_status_widget.setObjectName("serverStatusPanel")
            self.server_status_widget.setLayout(grid)
            self.server_status_widget.setMaximumWidth(340)
            self._apply_server_status_panel_style()
            self._server_status_servers = servers
            self._server_status_interval = interval_sec
            self._refresh_server_status()
            self.server_status_timer = QTimer(self)
            self.server_status_timer.timeout.connect(self._refresh_server_status)
            self.server_status_timer.start(interval_sec * 1000)

        center.addStretch()
        if self.server_status_widget:
            center.addWidget(self.server_status_widget)
        main_layout.addLayout(center)

        # === FOOTER ===
        footer = QHBoxLayout()

        self.version_button = QPushButton(self.tr("Launcher v{0}").format(LAUNCHER_VERSION))
        self.version_button.setFlat(True)
        self.version_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_button.setStyleSheet("color: #fff; border: none; background: none; text-align: left;")
        self.version_button.clicked.connect(self.show_about)
        footer.addWidget(self.version_button)

        self.pack_selector = QComboBox()
        self.packages_data = self.update_remote_packs()
        packages_list = self.packages_data.get("packages", [])
        selected_name = self.packages_data.get("selectedPackage", "")
        for i, pack in enumerate(packages_list):
            self.pack_selector.addItem(pack["title"], pack["name"])
            if pack["name"] == selected_name:
                self.pack_selector.setCurrentIndex(i)
        self.pack_selector.currentIndexChanged.connect(self.handle_modpack_change)
        if len(packages_list) == 1:
            pack_label = QLabel(packages_list[0]["title"])
            pack_label.setStyleSheet("color: #eee; font-size: 13px; padding: 6px 8px;")
            footer.addWidget(pack_label)
        else:
            footer.addWidget(self.pack_selector)

        self.optional_features_button = QPushButton(self.tr("Optional Features"))
        self.optional_features_button.clicked.connect(self.select_optional_features)
        footer.addWidget(self.optional_features_button)

        footer.addStretch()

        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setMinimumWidth(150)
        self.play_button.setEnabled(bool(self.account_data))
        self.play_button.clicked.connect(self.play_clicked)
        self.settings_button = QPushButton(self.tr("Settings"))
        self.settings_button.clicked.connect(self.open_settings_dialog)
        footer.addWidget(self.play_button)
        footer.addWidget(self.settings_button)

        main_layout.addLayout(footer)

        self.apply_material_theme()
        # Re-apply server status panel style so it isn't overridden by the main window stylesheet
        if self.server_status_widget:
            self._apply_server_status_panel_style()

    def _apply_server_status_panel_style(self):
        """Set card style on server status panel (called after theme so it takes effect)."""
        self.server_status_widget.setStyleSheet("""
            QWidget#serverStatusPanel {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
            }
            QWidget#serverStatusPanel QLabel {
                background: transparent;
                border: none;
                border-radius: 0;
            }
        """)

    def _styled_label(self, text, style_sheet, alignment):
        lbl = QLabel(text)
        lbl.setStyleSheet(style_sheet)
        lbl.setAlignment(alignment)
        return lbl

    def _motd_to_html(self, motd_str):
        """Convert Minecraft § color/format codes to HTML for tooltip display."""
        if not motd_str or not isinstance(motd_str, str):
            return ""
        # Minecraft: §0-9a-f = color, §k obfuscated, §l bold, §m strikethrough, §n underline, §o italic, §r reset
        colors = {
            "0": "#000000", "1": "#0000aa", "2": "#00aa00", "3": "#00aaaa", "4": "#aa0000",
            "5": "#aa00aa", "6": "#ffaa00", "7": "#aaaaaa", "8": "#555555", "9": "#5555ff",
            "a": "#55ff55", "b": "#55ffff", "c": "#ff5555", "d": "#ff55ff", "e": "#ffff55", "f": "#ffffff",
        }
        out = []
        i = 0
        current = {"color": "#fff", "bold": False, "italic": False, "underline": False, "strike": False}
        while i < len(motd_str):
            if motd_str[i] == "§" and i + 1 < len(motd_str):
                code = motd_str[i + 1].lower()
                i += 2
                if code == "r":
                    current = {"color": "#fff", "bold": False, "italic": False, "underline": False, "strike": False}
                elif code in colors:
                    current["color"] = colors[code]
                elif code == "l":
                    current["bold"] = True
                elif code == "o":
                    current["italic"] = True
                elif code == "n":
                    current["underline"] = True
                elif code == "m":
                    current["strike"] = True
                elif code == "k":
                    pass  # obfuscated: skip or keep as-is
                continue
            # Collect run of non-§ characters
            j = i
            while j < len(motd_str) and motd_str[j] != "§":
                j += 1
            chunk = motd_str[i:j]
            i = j
            if not chunk:
                continue
            escaped = html.escape(chunk).replace("\n", "<br/>")
            style = f"color:{current['color']}"
            if current["bold"]:
                style += ";font-weight:bold"
            if current["italic"]:
                style += ";font-style:italic"
            if current["underline"]:
                style += ";text-decoration:underline"
            if current["strike"]:
                style += ";text-decoration:line-through"
            out.append(f'<span style="{style}">{escaped}</span>')
        return "".join(out) if out else ""

    def _make_default_server_icon(self, w, h, online=True):
        """Default Minecraft-style server icon when server has no favicon."""
        pix = QPixmap(w, h)
        pix.fill(QColor(80, 80, 80) if online else QColor(60, 50, 50))
        painter = QPainter(pix)
        painter.setPen(QColor(100, 100, 100))
        painter.drawRect(0, 0, w - 1, h - 1)
        if online:
            painter.fillRect(4, 4, w - 8, h - 8, QColor(90, 120, 90))
        painter.end()
        return pix

    def _refresh_server_status(self):
        if not getattr(self, "_server_status_servers", None) or not self.server_status_rows:
            return
        if getattr(self, "_server_status_thread", None) and self._server_status_thread.isRunning():
            return
        self._server_status_thread = QThread()
        self._server_status_worker = ServerStatusWorker(self._server_status_servers)
        self._server_status_worker.moveToThread(self._server_status_thread)
        self._server_status_thread.started.connect(self._server_status_worker.run)
        self._server_status_worker.finished.connect(self._on_server_status_results)
        self._server_status_worker.finished.connect(self._server_status_thread.quit)
        self._server_status_worker.error.connect(self._server_status_thread.quit)
        self._server_status_thread.start()

    def _on_server_status_results(self, results):
        default_icon = getattr(self, "_server_status_default_icon", None)
        offline_icon = getattr(self, "_server_status_offline_icon", None)
        for i, (icon_lbl, name_lbl, status_lbl, players_lbl) in enumerate(self.server_status_rows):
            if i >= len(results):
                if offline_icon:
                    icon_lbl.setPixmap(offline_icon)
                name_lbl.setText(self.tr("—"))
                status_lbl.setText(self.tr("—"))
                players_lbl.setText(self.tr("—"))
                continue
            r = results[i]
            name = r.get("name", self.tr("Server"))
            # Icon: server favicon if present, else default
            favicon_b64 = r.get("favicon_b64")
            if favicon_b64:
                try:
                    data = base64.b64decode(favicon_b64)
                    pix = QPixmap()
                    if pix.loadFromData(data):
                        icon_lbl.setPixmap(pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    else:
                        icon_lbl.setPixmap(default_icon if r.get("online") else offline_icon)
                except Exception:
                    icon_lbl.setPixmap(default_icon if r.get("online") else offline_icon)
            else:
                icon_lbl.setPixmap(default_icon if r.get("online") else offline_icon)
            name_lbl.setText(name)
            if r.get("online"):
                status_lbl.setText(self.tr("● Online"))
                status_lbl.setStyleSheet("background: transparent; border: none; color: #7dd3a0; font-size: 12px;")
                p_online = r.get("players_online")
                p_max = r.get("players_max")
                players_lbl.setText(f"{p_online}/{p_max}" if p_online is not None and p_max is not None else self.tr("—"))
                players_lbl.setStyleSheet("background: transparent; border: none; color: #aaa; font-size: 12px;")
                raw = r.get("description_raw") or r.get("description") or self.tr("Online")
                tip = self._motd_to_html(raw) if raw else self.tr("Online")
                name_lbl.setToolTip(f"<p style='margin:0;'>{tip}</p>" if tip else self.tr("Online"))
            else:
                status_lbl.setText(self.tr("● Offline"))
                status_lbl.setStyleSheet("background: transparent; border: none; color: #e07c7c; font-size: 12px;")
                players_lbl.setText(self.tr("—"))
                players_lbl.setStyleSheet("background: transparent; border: none; color: #aaa; font-size: 12px;")
                name_lbl.setToolTip(self.tr(r.get("error", "Offline")))

    def load_bust(self, name, selected_uuid, accounts):
        cached_b64 = self.account_data.get("bust_base64")

        self.bust_thread = QThread()
        self.bust_worker = BustRenderWorker(name, cached_b64)
        self.bust_worker.moveToThread(self.bust_thread)

        self.bust_thread.started.connect(self.bust_worker.run)
        self.bust_worker.finished.connect(
            lambda pixmap, b64: self.on_bust_ready(pixmap, b64, selected_uuid, accounts))
        self.bust_worker.error.connect(
            lambda msg: print(f"[Bust Error] {msg}"))

        # Cleanup
        self.bust_worker.finished.connect(self.bust_thread.quit)
        self.bust_worker.finished.connect(self.bust_worker.deleteLater)
        self.bust_thread.finished.connect(self.bust_thread.deleteLater)

        self.bust_worker.error.connect(self.bust_thread.quit)
        self.bust_worker.error.connect(self.bust_worker.deleteLater)

        self.bust_thread.start()

    def on_bust_ready(self, pixmap: QPixmap, b64: str, selected_uuid: str, accounts: dict):
        self.bust_label.setPixmap(pixmap.scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

        # Update cache if needed
        if not self.account_data.get("bust_base64"):
            self.account_data["bust_base64"] = b64
            accounts["accounts"][selected_uuid] = self.account_data
            if self._accounts_file:
                with open(self._accounts_file, "w") as f:
                    json.dump(accounts, f, indent=4)

    def change_player_render(self):
        # Show loading image immediately
        loading_path = self._loading_path if self._loading_path and os.path.isfile(self._loading_path) else None
        loading_icon = QIcon(QPixmap(loading_path)) if loading_path else QIcon()
        self.player_render_button.setIcon(loading_icon)
        self.player_render_button.setIconSize(QSize(300, 300))
        self.player_render_button.setFixedSize(QSize(300, 300))

        # Create worker and thread
        self.render_thread = QThread()
        self.render_worker = PlayerRenderWorker(self.player_name)
        self.render_worker.moveToThread(self.render_thread)

        # Connect signals
        self.render_thread.started.connect(self.render_worker.run)
        self.render_worker.finished.connect(self.handle_render_success)
        self.render_worker.error.connect(self.handle_render_error)

        # Cleanup
        self.render_worker.finished.connect(self.render_thread.quit)
        self.render_worker.finished.connect(self.render_worker.deleteLater)
        self.render_thread.finished.connect(self.render_thread.deleteLater)

        self.render_worker.error.connect(self.render_thread.quit)
        self.render_worker.error.connect(self.render_worker.deleteLater)

        # Start
        self.render_thread.start()

    def handle_render_success(self, pixmap: QPixmap):
        self.player_render_button.setIcon(QIcon(pixmap.scaled(
            300, 300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )))

    def handle_render_error(self, message: str):
        print(f"[Render Error] {message}")
        # Optionally show an error image or restore old one

    def select_optional_features(self):
        selected_index = self.pack_selector.currentIndex()
        selected_name = self.pack_selector.itemData(selected_index)

        selected_pack = next(
            (p for p in self.packages_data["packages"]
             if p["name"] == selected_name),
            None
        )

        if not selected_pack:
            return

        # Download remote index
        package_base = self.config.get("package_base_url", "").rstrip("/")
        index_url = urljoin(package_base + "/", selected_pack["location"])
        try:
            response = requests.get(index_url)
            response.raise_for_status()
            index_json = response.json()
        except Exception as e:
            print(f"Failed to fetch index: {e}")
            return

        optional_features = index_json.get("optionalFeatures", [])
        if not optional_features:
            print("No optional features available.")
            return

        dialog = OptionalFeatureSelectorDialog(
            optional_features, already_selected_features=selected_pack.get("optionalFeatures", []), icon_path=self._icon_path)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        if dialog.exec():
            selected_optional = dialog.get_selected_features()
            selected_pack["optionalFeatures"] = selected_optional
            self.save_packages()

    def play_clicked(self):
        # Step 1: Clean up previous update thread if running
        if hasattr(self, "update_thread") and self.update_thread is not None:
            if self.update_thread.isRunning():
                self.update_worker.cancel_requested = True  # graceful stop
                self.update_thread.quit()
                self.update_thread.wait()

            self.update_thread.deleteLater()
            self.update_worker = None
            self.update_thread = None

        # 🎮 Step 2: Continue with new update setup
        selected_index = self.pack_selector.currentIndex()
        selected_name = self.pack_selector.itemData(selected_index)

        selected_pack = next(
            (p for p in self.packages_data["packages"]
             if p["name"] == selected_name),
            None
        )

        if not selected_pack:
            return

        selected_optional_features = selected_pack.get("optionalFeatures", [])

        self.log_window = LogWindow(icon_path=self._icon_path)
        self.log_window.setWindowFlag(Qt.WindowType.Window, True)
        self.log_window.finished.connect(self.show)
        self.log_window.canceled.connect(self.show)
        self.log_window.show()

        # 🌱 Create new thread + worker
        package_base = self.config.get("package_base_url", "").rstrip("/")
        self.update_thread = QThread()
        self.update_worker = UpdateModpackWorker(
            selected_pack, package_base, selected_optional_features,
            packs_dir=self._packs_dir
        )
        self.update_worker.moveToThread(self.update_thread)

        # 🔌 Connect signals
        self.update_worker.status_update.connect(self.log_window.set_status)
        self.update_worker.error.connect(
            lambda msg: self.log_window.set_status(f"[ERROR] {msg}")
        )
        self.update_worker.finished.connect(self.launch_game)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)

        self.update_thread.started.connect(self.update_worker.run)
        self.update_thread.start()

    def file_matches(self, path, expected_sha512):
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            return hashlib.sha512(f.read()).hexdigest() == expected_sha512

    def download_file(self, url, dest_path):
        try:
            r = requests.get(url, stream=True)
            r.raise_for_status()
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        except Exception as e:
            self.log_window.set_status(
                f"<b style='color:red;'>Failed to download {url}: {e}</b>")

    def on_update_finished(self, pack_index, base_dir):
        selected_features = self.update_worker.selected_optional_features

        for pack in self.packages_data["packages"]:
            if pack["name"] == pack_index.get("id"):
                pack["optionalFeatures"] = selected_features
                break

        self.save_packages()  # Make sure this writes to disk

    def save_packages(self):
        if self._packages_file:
            with open(self._packages_file, "w") as f:
                json.dump(self.packages_data, f, indent=4)

    def launch_game(self, pack_index, base_dir):
        self.on_update_finished(pack_index, base_dir)
        if self.config.get("general", {}).get("close_launcher_on_play", True):
            self.hide()
        deps = pack_index.get("dependencies", {})
        mc_version = deps.get("minecraft", "").strip()
        # Resolve loader: neoforge (preferred), forge, fabric-loader, quilt
        loader_id = None
        loader_version = None
        for key in ("neoforge", "forge", "fabric-loader", "quilt"):
            if deps.get(key):
                raw = deps[key].strip()
                if not raw:
                    continue
                loader_id = key
                # Legacy forge format "1.20.1-47.3.12" -> loader_version "47.3.12"
                if key in ("forge", "neoforge") and "-" in raw and raw.startswith(mc_version + "-"):
                    loader_version = raw[len(mc_version) + 1 :].strip()
                else:
                    loader_version = raw
                break
        if not loader_id or not loader_version or not mc_version:
            self.log_window.set_status(self.tr("[ERROR] Pack dependencies must include minecraft and one of: neoforge, forge, fabric-loader, quilt."))
            return

        # Load user account
        with open(self._accounts_file, "r") as f:
            accounts = json.load(f)
        selected_uuid = accounts["selected"]
        login_data = accounts["accounts"][selected_uuid]

        # Build launch options
        options = {
            "username": login_data["name"],
            "uuid": login_data["id"],
            "token": login_data["access_token"],
            "gameDirectory": base_dir,
            "launcherName": self.config.get("launcher_name", "Matteino Launcher"),
            "launcherVersion": LAUNCHER_VERSION
        }

        # Apply modpack settings (pack index overrides config)
        mc_cfg = self.config.get("minecraft", {})
        settings = pack_index.get("settings", {})
        min_ram = int(settings.get("min_ram", mc_cfg.get("min_ram_mb", 2048)))
        max_ram = int(settings.get("max_ram", mc_cfg.get("max_ram_mb", 4096)))
        jvm_args = [
            f"-Xms{min_ram}M",
            f"-Xmx{max_ram}M"
        ] + settings.get("jvm_args", "").split()
        # Append user config JVM args (Settings → Custom JVM arguments)
        extra_jvm = (mc_cfg.get("jvm_args") or "").strip()
        if extra_jvm:
            jvm_args.extend(extra_jvm.split())

        java_path = settings.get("java_path") or mc_cfg.get("java_path")
        if java_path:
            options["javaPath"] = java_path

        options["jvmArguments"] = jvm_args

        self.log_window.set_status(
            self.tr("Ensuring Minecraft + mod loader are installed..."))

        self.install_thread = QThread()
        self.install_worker = MCModLoaderInstallerWorker(
            base_dir, mc_version, loader_id, loader_version
        )
        self.install_worker.moveToThread(self.install_thread)

        self.install_worker.status_update.connect(self.log_window.set_status)
        self.install_worker.progress_update.connect(
            self.log_window.set_progress)
        self.install_worker.progress_update_max.connect(
            self.log_window.set_max_progress)
        self.install_worker.error.connect(
            lambda msg: self.log_window.set_status(self.tr("[ERROR] {0}").format(msg)))

        def on_install_finished(version_id):
            self.launch_minecraft_after_update(version_id, base_dir, options)

        self.install_worker.finished.connect(on_install_finished)
        self.install_worker.finished.connect(self.install_thread.quit)
        self.install_worker.finished.connect(self.install_worker.deleteLater)
        self.install_thread.finished.connect(self.install_thread.deleteLater)

        self.install_thread.started.connect(self.install_worker.run)
        self.install_thread.start()

    def launch_minecraft_after_update(self, version_id, base_dir, options):
        # Sync launcher config servers into Minecraft server list (servers.dat)
        server_status_cfg = self.config.get("server_status") or {}
        if server_status_cfg.get("servers"):
            merge_config_servers(base_dir, server_status_cfg["servers"])
        # Build command
        command = get_minecraft_command(
            version_id, base_dir, options)

        # Launch Minecraft in LogWindow
        self.log_window.set_status(self.tr("Launching Minecraft..."))
        self.log_window.start_process(command[1:])

    def handle_modpack_change(self, index):
        selected_name = self.pack_selector.itemData(index)

        # Update local file
        try:
            if self._packages_file and os.path.exists(self._packages_file):
                with open(self._packages_file, "r") as f:
                    data = json.load(f)
            else:
                data = {"packages": []}

            data["selectedPackage"] = selected_name

            if self._packages_file:
                with open(self._packages_file, "w") as f:
                    json.dump(data, f, indent=4)

        except Exception as e:
            print(f"Failed to save selected pack: {e}")

    def show_about(self):
        launcher_name = self.config.get("window_title", "Matteino Launcher")
        dialog = AboutDialog(parent=self, launcher_name=launcher_name, icon_path=self._icon_path)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.exec()

    def open_settings_dialog(self):
        def on_save_config(override):
            common_config.save_user_config("user", override)
            self.config = common_config.load_config("user")

        def on_save_translations_and_restart(trans):
            common_config.save_user_config("user", {"translations": trans})
            os.execv(sys.executable, [sys.executable] + sys.argv)

        dialog = SettingsDialog(
            settings_file=self.paths.get("settings_file"),
            icon_path=self._icon_path,
            config=self.config,
            save_minecraft_callback=on_save_config,
            save_translations_and_restart_callback=on_save_translations_and_restart,
        )
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.exec()

    def update_remote_packs(self):
        package_base = self.config.get("package_base_url", "").rstrip("/")
        packages_url = f"{package_base}/packages.json" if package_base else ""
        if not packages_url:
            if self._packages_file and os.path.exists(self._packages_file):
                with open(self._packages_file, "r") as f:
                    return json.load(f)
            return {"packages": [], "selectedPackage": ""}
        try:
            response = requests.get(packages_url, timeout=10)
            response.raise_for_status()

            remote_data = response.json()

            # Load local copy
            if self._packages_file and os.path.exists(self._packages_file):
                with open(self._packages_file, "r") as f:
                    local_data = json.load(f)
            else:
                local_data = {"packages": [],
                              "selectedPackage": "", "optionalFeatures": {}}

            # Merge user selections per-pack
            local_packs_by_name = {
                p["name"]: p for p in local_data.get("packages", [])
            }

            for remote_pack in remote_data.get("packages", []):
                name = remote_pack.get("name")
                local_pack = local_packs_by_name.get(name)
                if local_pack and "optionalFeatures" in local_pack:
                    remote_pack["optionalFeatures"] = local_pack["optionalFeatures"]
                elif "optionalFeatures" not in remote_pack:
                    remote_pack["optionalFeatures"] = []

            # Also preserve selectedPackage globally
            if "selectedPackage" in local_data:
                remote_data["selectedPackage"] = local_data["selectedPackage"]

            # Write merged result
            if self._packages_file:
                with open(self._packages_file, "w") as f:
                    json.dump(remote_data, f, indent=4)

            return remote_data

        except Exception as e:
            print(f"Failed to fetch remote packages: {e}")
            if self._packages_file and os.path.exists(self._packages_file):
                with open(self._packages_file, "r") as f:
                    return json.load(f)
            return {"packages": [], "selectedPackage": ""}

    def reopen_auth_browser(self):
        if self.current_login_url:
            webbrowser.open(self.current_login_url)

    def open_auth_browser(self):
        ms = self.config.get("microsoft", {})
        client_id = ms.get("client_id", "")
        redirect_url = ms.get("redirect_url", "http://localhost:2411")
        if not client_id:
            print("Microsoft client_id not set. Set it in user.config.json or LAUNCHER_MICROSOFT_CLIENT_ID.")
            return
        login_url, state, code_verifier = minecraft_launcher_lib.microsoft_account.get_secure_login_data(
            client_id, redirect_url
        )
        self.mc_state = state
        self.mc_code_verifier = code_verifier
        self.current_login_url = login_url

        threading.Thread(target=self.wait_for_login, args=(
            code_verifier,), daemon=True).start()
        webbrowser.open(login_url)

        # Update buttons visibility if they exist
        if hasattr(self, 'login_button'):
            self.login_button.setEnabled(False)

        if hasattr(self, 'reopen_button'):
            self.reopen_button.setVisible(True)

    def wait_for_login(self, code_verifier):
        ms = self.config.get("microsoft", {})
        logo_path = os.path.abspath(self._logo_path) if (self._logo_path and os.path.isfile(self._logo_path)) else None
        login_data = start_temp_server(
            code_verifier,
            ms.get("client_id", ""),
            ms.get("client_secret", ""),
            ms.get("redirect_url", "http://localhost:2411"),
            int(ms.get("redirect_port", 2411)),
            logo_path=logo_path,
        )
        self.login_success_signal.emit(login_data)

    def handle_login_success(self, login_data):
        uuid = login_data["id"]
        name = login_data["name"]
        access_token = login_data["access_token"]

        accounts = {"accounts": {uuid: login_data}, "selected": uuid}
        if self._accounts_file:
            with open(self._accounts_file, "w") as f:
                json.dump(accounts, f, indent=4)

        self.player_name = name
        self.refresh_ui()
        # Optional: if login_button or reopen_button exist, hide them
        if hasattr(self, 'login_button'):
            self.login_button.setVisible(False)
        if hasattr(self, 'reopen_button'):
            self.reopen_button.setVisible(False)

    def refresh_ui(self):
        self.centralWidget().deleteLater()
        self.setup_ui()

    def show_account_chooser(self):
        if not self._accounts_file or not os.path.exists(self._accounts_file):
            return

        with open(self._accounts_file, "r") as f:
            accounts = json.load(f)

        dialog = AccountSelectorDialog(accounts, self._accounts_file, icon_path=self._icon_path, parent=self)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        if dialog.exec():
            selected_uuid = dialog.selected_uuid
            if selected_uuid == "new":
                self.open_auth_browser()
            elif selected_uuid:
                accounts["selected"] = selected_uuid
                if self._accounts_file:
                    with open(self._accounts_file, "w") as f:
                        json.dump(accounts, f, indent=4)
                self.refresh_ui()
