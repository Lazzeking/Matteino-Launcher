# widgets/mod_search_dialog.py
"""
Modal to search mods on Modrinth and CurseForge and add them to the pack.
Provider logos are loaded from each site and cached as PNG under writable_dir.
"""

import os
import tempfile
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QComboBox, QLabel, QScrollArea, QWidget, QFrame, QGridLayout,
    QSpinBox,
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon

from src.common import paths as common_paths
from workers.mod_search_worker import ModSearchWorker, PAGE_SIZE

# Provider icon URLs: primary (official site), then fallback PNG if primary fails to decode (e.g. ICO on Linux)
PROVIDER_ICON_URLS = {
    "modrinth": ["https://modrinth.com/favicon.ico"],
    "curseforge": [
        "https://www.curseforge.com/favicon.ico",
        "https://images.icon-icons.com/3911/PNG/128/curseforge_logo_icon_247241.png",  # fallback PNG
    ],
}

ICON_SIZE = 20


def _provider_icon_cache_dir() -> str:
    """Directory for cached provider icons (PNG). Created on first use."""
    d = os.path.join(common_paths.writable_dir(), "launcherAdmin", "cache", "provider_icons")
    os.makedirs(d, exist_ok=True)
    return d


def _load_icon_from_bytes(data: bytes, content_type: str = "") -> QPixmap | None:
    """Decode image bytes to QPixmap. Tries loadFromData; if that fails (e.g. ICO on Linux), try temp file + QPixmap or QIcon."""
    pix = QPixmap()
    if pix.loadFromData(data) and not pix.isNull():
        return pix
    # ICO often fails with loadFromData on Linux; try loading from temp file (Qt may use file extension)
    is_ico = "ico" in (content_type or "").lower() or data[:4] == b"\x00\x00\x01\x00"
    suffix = ".ico" if is_ico else ".png"
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            path = f.name
        # Some Qt builds load ICO from file when loadFromData fails
        px = QPixmap(path)
        if not px.isNull():
            return px
        # Fallback: QIcon can load ICO from file, then extract pixmap
        icon = QIcon(path)
        px = icon.pixmap(ICON_SIZE * 2, ICON_SIZE * 2)
        return px if not px.isNull() else None
    except Exception:
        return None
    finally:
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except Exception:
                pass


class ResultIconWorker(QObject):
    """Fetches one result row icon in a background thread. Emits loaded(id, pixmap) on main thread."""
    loaded = pyqtSignal(int, object)  # id, QPixmap or None

    def __init__(self, icon_id: int, icon_url: str, parent=None):
        super().__init__(parent)
        self.icon_id = icon_id
        self.icon_url = icon_url

    def run(self):
        pix = None
        try:
            if self.icon_url:
                r = requests.get(self.icon_url, timeout=5)
                if r.ok:
                    pix = QPixmap()
                    if pix.loadFromData(r.content) and not pix.isNull():
                        pix = pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    else:
                        pix = None
        except Exception:
            pass
        self.loaded.emit(self.icon_id, pix)


class ModSearchDialog(QDialog):
    """Search Modrinth and/or CurseForge and add selected mods to the pack."""

    def __init__(self, parent=None, game_version: str = "", loader: str = "", curseforge_api_key: str = "", on_add_mod=None, installed_mod_ids=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Search mods"))
        self.setMinimumSize(640, 500)
        self._game_version = game_version
        self._loader = loader
        self._curseforge_api_key = curseforge_api_key
        self._on_add_mod = on_add_mod
        # Set of (provider, project_id) for mods already in the pack
        self._installed_ids = set(installed_mod_ids) if installed_mod_ids else set()
        self._search_thread = None
        self._worker = None
        self._current_page = 0
        self._total_count = 0
        self._last_query = ""
        self._icon_labels = {}  # id -> QLabel for result row icons (cleared when results are cleared)
        self._next_icon_id = 0
        self._icon_threads = []  # keep refs so threads aren't garbage-collected
        # Session cache: (query, provider, page) -> (hits, total); used when switching pages
        self._page_cache = {}
        self._total_pages = 0  # for go-to-page spinbox max

        layout = QVBoxLayout(self)

        # Search row
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Search by name or description..."))
        self.search_input.returnPressed.connect(self.run_search)
        search_row.addWidget(self.search_input)

        self.provider_combo = QComboBox()
        self._provider_icons = {}
        self._load_provider_icons()
        self.provider_combo.addItem(self.tr("Modrinth"), "modrinth")
        self.provider_combo.addItem(self.tr("CurseForge"), "curseforge")
        self.provider_combo.addItem(self.tr("Both"), "both")
        search_row.addWidget(QLabel(self.tr("Provider:")))
        search_row.addWidget(self.provider_combo)

        self.search_btn = QPushButton(self.tr("Search"))
        self.search_btn.clicked.connect(self.run_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # Filters hint
        if game_version or loader:
            parts = []
            if game_version:
                parts.append(f"Minecraft {game_version}")
            if loader:
                parts.append(loader)
            filter_lbl = QLabel(self.tr("Filters: {filters}").format(filters=", ".join(parts)))
            filter_lbl.setStyleSheet("color: #888; font-size: 9pt;")
            layout.addWidget(filter_lbl)

        # Results
        layout.addWidget(QLabel(self.tr("Results:")))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(4)
        self.scroll.setWidget(self.results_container)
        layout.addWidget(self.scroll)

        # Pagination
        pagination_row = QHBoxLayout()
        self.prev_btn = QPushButton(self.tr("Previous"))
        self.prev_btn.clicked.connect(self._prev_page)
        self.prev_btn.setEnabled(False)
        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #888;")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setValue(1)
        self.page_spin.setToolTip(self.tr("Go to page"))
        self.page_spin.valueChanged.connect(self._go_to_page)
        self.page_spin.setEnabled(False)
        self.next_btn = QPushButton(self.tr("Next"))
        self.next_btn.clicked.connect(self._next_page)
        self.next_btn.setEnabled(False)
        pagination_row.addWidget(self.prev_btn)
        pagination_row.addStretch()
        pagination_row.addWidget(self.page_label)
        pagination_row.addWidget(self.page_spin)
        pagination_row.addStretch()
        pagination_row.addWidget(self.next_btn)
        layout.addLayout(pagination_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

    def _load_provider_icons(self):
        """Load provider icons from cache or from official site, then cache as PNG. Processes every provider."""
        icons = {}
        cache_dir = _provider_icon_cache_dir()
        for provider, urls in list(PROVIDER_ICON_URLS.items()):
            urls = [urls] if isinstance(urls, str) else urls
            cache_path = os.path.join(cache_dir, f"provider_icon_{provider}.png")
            pix = None
            if os.path.isfile(cache_path):
                pix = QPixmap(cache_path)
            if pix is None or pix.isNull():
                for url in urls:
                    try:
                        r = requests.get(url, timeout=5)
                        if not r.ok:
                            continue
                        content_type = (r.headers.get("content-type") or "").strip().lower()
                        pix = _load_icon_from_bytes(r.content, content_type)
                        if pix is not None and not pix.isNull():
                            try:
                                png = pix.scaled(ICON_SIZE * 2, ICON_SIZE * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                png.save(cache_path)
                            except Exception:
                                pass
                            break
                    except Exception:
                        continue
            if pix is not None and not pix.isNull():
                scaled = pix.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icons[provider] = QIcon(scaled)
        self._provider_icons = icons

    def _set_provider_combo_icons(self):
        for i in range(self.provider_combo.count()):
            key = self.provider_combo.itemData(i)
            if key and key in self._provider_icons:
                self.provider_combo.setItemIcon(i, self._provider_icons[key])

    def run_search(self):
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText(self.tr("Enter a search term."))
            return

        self._last_query = query
        self._current_page = 0
        self._do_search()

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._do_search()

    def _next_page(self):
        self._current_page += 1
        self._do_search()

    def _go_to_page(self, value: int):
        """Jump to 1-based page number (from spinbox)."""
        page0 = value - 1
        if page0 == self._current_page:
            return
        self._current_page = page0
        self._do_search()

    def _cache_key(self):
        return self._cache_key_for_page(self._current_page)

    def _cache_key_for_page(self, page: int):
        provider = self.provider_combo.currentData() or "modrinth"
        return (self._last_query, provider, page)

    def _do_search(self):
        provider = self.provider_combo.currentData() or "modrinth"
        cache_key = self._cache_key()

        # Use session cache if we have this page already (instant when switching back)
        if cache_key in self._page_cache:
            hits, total = self._page_cache[cache_key]
            self._clear_results()
            self._apply_results(self._current_page, hits, total)
            self._prefetch_next_page()
            return

        self.status_label.setText(self.tr("Searching..."))
        self.search_btn.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.page_spin.setEnabled(False)
        self._clear_results()

        self._search_thread = QThread()
        self._worker = ModSearchWorker(
            query=self._last_query,
            provider=provider,
            page=self._current_page,
            game_version=self._game_version,
            loader=self._loader,
            curseforge_api_key=self._curseforge_api_key,
        )
        self._worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results)
        self._worker.finished.connect(self._search_thread.quit)
        self._worker.error.connect(self._on_search_error)
        self._search_thread.start()

    def _prefetch_next_page(self):
        """Prefetch next page in background so it's instant when user clicks Next."""
        provider = self.provider_combo.currentData() or "modrinth"
        next_page = self._current_page + 1
        key = (self._last_query, provider, next_page)
        if not self._last_query or key in self._page_cache:
            return
        thread = QThread()
        worker = ModSearchWorker(
            query=self._last_query,
            provider=provider,
            page=next_page,
            game_version=self._game_version,
            loader=self._loader,
            curseforge_api_key=self._curseforge_api_key,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_prefetch_done)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._prefetch_thread = thread
        self._prefetch_worker = worker

    def _on_prefetch_done(self, page: int, hits: list, total: int):
        """Store prefetched page in cache; do not update UI."""
        self._page_cache[self._cache_key_for_page(page)] = (hits, total)

    def _on_search_error(self, msg: str):
        self.status_label.setText(msg)
        self.search_btn.setEnabled(True)
        self.prev_btn.setEnabled(self._current_page > 0)
        self.next_btn.setEnabled(False)
        self._update_page_spin_state(0)

    def _on_results(self, page: int, hits: list, total: int):
        """Called when a search worker finishes. Cache result; update UI only if this is the current page."""
        self._page_cache[self._cache_key_for_page(page)] = (hits, total)

        # Only update UI if this response is for the page we're showing
        if page != self._current_page:
            return

        self._apply_results(page, hits, total)
        self._prefetch_next_page()

    def _apply_results(self, page: int, hits: list, total: int):
        """Fill UI with hits and update pagination state. Call after cache hit or when worker finishes for current page."""
        self.search_btn.setEnabled(True)
        self._total_count = total
        self._total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 0
        self.prev_btn.setEnabled(page > 0)
        self.next_btn.setEnabled(page < self._total_pages - 1 and len(hits) >= PAGE_SIZE)
        self._update_page_spin_state(self._total_pages)

        if not hits:
            self.status_label.setText(self.tr("No results."))
            self.page_label.setText("")
            return

        self.page_label.setText(self.tr("Page {page} of {total}").format(page=page + 1, total=max(1, self._total_pages)))
        self.status_label.setText(self.tr("{n} result(s).").format(n=len(hits)))
        self._current_hits = hits
        for hit in hits:
            self._add_result_row(hit)

    def _update_page_spin_state(self, total_pages: int):
        """Enable/disable and set range of the go-to-page spinbox."""
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, total_pages))
        self.page_spin.setValue(self._current_page + 1)
        self.page_spin.setEnabled(total_pages > 0)
        self.page_spin.blockSignals(False)

    def _clear_results(self):
        self._icon_labels.clear()
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_result_row(self, hit: dict):
        row = QFrame()
        row.setStyleSheet("QFrame { background-color: #2a2a2a; border: none; border-radius: 2px; }")
        row.setMinimumHeight(56)
        grid = QGridLayout(row)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(8)

        # Icon: plain image, no border; load in background so UI stays responsive
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setScaledContents(False)
        icon_url = hit.get("icon_url", "")
        if icon_url:
            icon_id = self._next_icon_id
            self._next_icon_id += 1
            self._icon_labels[icon_id] = icon_label
            thread = QThread()
            worker = ResultIconWorker(icon_id, icon_url)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.loaded.connect(self._on_result_icon_loaded)
            worker.loaded.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.start()
            self._icon_threads.append(thread)
            thread.finished.connect(lambda t=thread: self._icon_threads.remove(t) if t in self._icon_threads else None)
        grid.addWidget(icon_label, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Title and description: no borders, left-aligned
        title = QLabel(hit.get("title", ""))
        title.setStyleSheet("font-weight: bold; color: #eee; background: transparent; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(title, 0, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        desc = QLabel((hit.get("description") or "")[:120] + ("..." if len(hit.get("description") or "") > 120 else ""))
        desc.setStyleSheet("color: #aaa; font-size: 9pt; background: transparent; border: none;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.addWidget(desc, 1, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Provider: cached icon + name
        provider_key = (hit.get("provider") or "").lower()
        prov_box = QWidget()
        prov_layout = QHBoxLayout(prov_box)
        prov_layout.setContentsMargins(0, 0, 0, 0)
        prov_layout.setSpacing(4)
        if provider_key in self._provider_icons:
            prov_icon_label = QLabel()
            prov_icon_label.setFixedSize(16, 16)
            prov_icon_label.setPixmap(
                self._provider_icons[provider_key].pixmap(16, 16)
            )
            prov_icon_label.setStyleSheet("background: transparent; border: none;")
            prov_layout.addWidget(prov_icon_label)
        prov = QLabel(hit.get("provider", "").title())
        prov.setStyleSheet("color: #888; font-size: 8pt; background: transparent; border: none;")
        prov_layout.addWidget(prov)
        prov_layout.addStretch()
        grid.addWidget(prov_box, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        provider = (hit.get("provider") or "").lower()
        project_id = str(hit.get("project_id") or "")
        already_installed = (provider, project_id) in self._installed_ids

        if already_installed:
            already_lbl = QLabel(self.tr("Already installed"))
            already_lbl.setStyleSheet("color: #6a6; font-size: 9pt; background: transparent; border: none;")
            grid.addWidget(already_lbl, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        else:
            add_btn = QPushButton(self.tr("Add to pack"))
            add_btn.clicked.connect(lambda checked=False, h=hit: self._add_mod(h))
            grid.addWidget(add_btn, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        self.results_layout.addWidget(row)

    def _on_result_icon_loaded(self, icon_id: int, pixmap: QPixmap | None):
        """Called on main thread when a result row icon fetch finishes."""
        label = self._icon_labels.pop(icon_id, None)
        if label and pixmap and not pixmap.isNull():
            label.setPixmap(pixmap)

    def _add_mod(self, hit: dict):
        if self._on_add_mod:
            self._on_add_mod(hit)
        provider = (hit.get("provider") or "").lower()
        project_id = str(hit.get("project_id") or "")
        self._installed_ids.add((provider, project_id))
        # Re-render current page so this row shows "Already installed"
        if getattr(self, "_current_hits", None):
            self._clear_results()
            self._apply_results(self._current_page, self._current_hits, self._total_count)
        self.status_label.setText(self.tr("Added '{title}'. Add more or close.").format(title=hit.get("title", "")))

    def showEvent(self, event):
        super().showEvent(event)
        self._set_provider_combo_icons()
