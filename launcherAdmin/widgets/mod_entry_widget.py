# widgets/mod_entry_widget.py

import hashlib
import os
import requests
from io import BytesIO
from PyQt6.QtWidgets import (
    QFrame, QLabel, QPushButton, QGridLayout, QHBoxLayout, QSizePolicy
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread
import webbrowser


def _icon_cache_path(cache_dir: str, icon_url: str) -> str:
    """Path for cached icon: cache_dir/<sha256(url)>.png"""
    name = hashlib.sha256(icon_url.encode()).hexdigest() + ".png"
    return os.path.join(cache_dir, name)


class IconFetchWorker(QObject):
    """Fetches a single icon URL in a background thread; optionally saves to cache. Emits icon_loaded when done."""
    icon_loaded = pyqtSignal(object)  # QPixmap or None

    def __init__(self, url: str, cache_path: str | None = None):
        super().__init__()
        self.url = url
        self.cache_path = cache_path

    def run(self):
        pixmap = None
        try:
            if self.url:
                response = requests.get(self.url, timeout=3)
                response.raise_for_status()
                data = response.content
                if self.cache_path:
                    os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                    with open(self.cache_path, "wb") as f:
                        f.write(data)
                pixmap = QPixmap()
                pixmap.loadFromData(data)
        except Exception:
            pass
        self.icon_loaded.emit(pixmap)


class ModEntryWidget(QFrame):
    def __init__(self, mod_data: dict, on_edit=None, on_remove=None, compact=False, readonly=False, icon_cache_dir: str | None = None, icon_thread_registry=None):
        super().__init__()

        self.mod_data = mod_data
        self.on_edit = on_edit
        self.on_remove = on_remove
        self.compact = compact
        self.readonly = readonly
        self.icon_cache_dir = icon_cache_dir
        self.icon_thread_registry = icon_thread_registry  # window with register_icon_thread / unregister_icon_thread

        self.setObjectName("ModEntry")

        base_style = """
        #ModEntry {
            background-color: #2e2e2e;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 8px;
            margin-bottom: 6px;
        }
        QLabel {
            color: #dddddd;
        }
        QPushButton {
            padding: 2px 8px;
            font-size: 9pt;
        }
        QPushButton:hover {
            background-color: #444;
        }
        """

        compact_additions = """
        #ModEntry {
            padding: 3px;
            margin-bottom: 4px;
        }
        QLabel {
            font-size: 9pt;
        }
        QPushButton {
            padding: 1px 5px;
            font-size: 8pt;
        }
        """

        self.setStyleSheet(
            base_style + (compact_additions if self.compact else ""))

        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(4)
        self.setLayout(layout)

        # === Icon (row 0, col 0) – from cache if present, else load async and cache ===
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        layout.addWidget(self._icon_label, 0, 0, 2, 1,
                         alignment=Qt.AlignmentFlag.AlignTop)
        icon_url = mod_data.get("icon_url", "")
        if icon_url:
            cache_path = _icon_cache_path(self.icon_cache_dir, icon_url) if self.icon_cache_dir else None
            if cache_path and os.path.isfile(cache_path):
                try:
                    pixmap = QPixmap(cache_path)
                    if not pixmap.isNull():
                        self._icon_label.setPixmap(pixmap.scaled(
                            24, 24, Qt.AspectRatioMode.KeepAspectRatio))
                except Exception:
                    self._start_icon_fetch(icon_url, cache_path)
            else:
                self._start_icon_fetch(icon_url, cache_path)
        # else: leave icon empty

        # === Title (row 0, col 1) ===
        title_label = QLabel(mod_data.get("title", self.tr("Unknown Mod")))
        title_label.setStyleSheet("font-weight: bold; font-size: 10.5pt;")
        layout.addWidget(title_label, 0, 1,
                         alignment=Qt.AlignmentFlag.AlignLeft)

        # === Host link (row 0, col 2) ===
        host = self.get_host(mod_data)
        url = mod_data.get("url", "") or ""
        if url:
            host_label = QLabel(f'<a href="{url}">{host}</a>')
            host_label.setOpenExternalLinks(True)
        else:
            host_label = QLabel(host)
        host_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        host_label.setStyleSheet("color: #4da6ff")
        layout.addWidget(host_label, 0, 2,
                         alignment=Qt.AlignmentFlag.AlignRight)

        # === Version (row 1, col 1) ===
        if "version_number" in mod_data and mod_data["version_number"]:
            version = mod_data["version_number"]
        else:
            downloads = mod_data.get("downloads") or [""]
            version = mod_data.get("path", "") or (downloads[0] if downloads else "").split("/")[-1]
        version_label = QLabel(f"Version: {version}")
        version_label.setStyleSheet("font-family: monospace; font-size: 9pt;")
        layout.addWidget(version_label, 1, 1,
                         alignment=Qt.AlignmentFlag.AlignLeft)

        # === Button bar (row 1, col 2) ===
        if not self.readonly:
            btn_row = QHBoxLayout()
            if self.on_edit:
                edit_btn = QPushButton(self.tr("Edit"))
                edit_btn.clicked.connect(lambda: self.on_edit(mod_data))
                btn_row.addWidget(edit_btn)

            if self.on_remove:
                remove_btn = QPushButton(self.tr("Remove"))
                remove_btn.clicked.connect(lambda: self.on_remove(mod_data))
                btn_row.addWidget(remove_btn)

            btn_container = QFrame()
            btn_container.setLayout(btn_row)
            layout.addWidget(btn_container, 1, 2,
                             alignment=Qt.AlignmentFlag.AlignRight)

        # === Description (row 2, col 0 → span 3 cols) ===
        desc_label = QLabel(mod_data.get(
            "description", self.tr("No description")))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #aaa; font-size: 9pt;")
        desc_label.setMaximumHeight(40)
        layout.addWidget(desc_label, 2, 0, 1, 3)

        # === Dependencies (row 3+, col 0 → span 3 cols) ===
        dependencies = self.mod_data.get("dependencies", [])
        dep_row = 3
        if dependencies:
            req = [d["name"]
                   for d in dependencies if d.get("type") == "required"]
            opt = [d["name"]
                   for d in dependencies if d.get("type") == "optional"]

            if req:
                label_req = QLabel(
                    self.tr("<i>Requires:</i> {mods}").format(mods=', '.join(req)))
                label_req.setStyleSheet("color: #777; font-size: 10px;")
                layout.addWidget(label_req, dep_row, 0, 1, 3)
                dep_row += 1

            if opt:
                label_opt = QLabel(
                    self.tr("<i>Optionals:</i> {mods}").format(mods=', '.join(opt)))
                label_opt.setStyleSheet("color: #999; font-size: 10px;")
                layout.addWidget(label_opt, dep_row, 0, 1, 3)

    def _start_icon_fetch(self, url: str, cache_path: str | None = None):
        """Start loading the icon in a background thread; save to cache_path if provided; update label when done."""
        thread = QThread()
        worker = IconFetchWorker(url, cache_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.icon_loaded.connect(self._on_icon_loaded)
        worker.icon_loaded.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Register with workspace window so closeEvent can quit/wait (widget has no parent yet in __init__)
        registry = self.icon_thread_registry
        if registry and getattr(registry, "register_icon_thread", None):
            registry.register_icon_thread(thread)
            thread.finished.connect(
                lambda: getattr(registry, "unregister_icon_thread", lambda _: None)(thread)
            )
        thread.start()
        self._icon_thread = thread
        self._icon_worker = worker

    def _on_icon_loaded(self, pixmap):
        """Called from main thread when icon fetch finishes."""
        if pixmap and self._icon_label:
            self._icon_label.setPixmap(pixmap.scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio))

    def get_host(self, mod_data):
        url = mod_data.get("url", "")
        if "modrinth.com" in url:
            return "Modrinth"
        elif "curseforge.com" in url or "forgecdn.net" in "".join(mod_data.get("downloads", [])):
            return "CurseForge"
        return self.tr("Custom")
