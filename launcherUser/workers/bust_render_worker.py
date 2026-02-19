from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
import base64
import requests


class BustRenderWorker(QObject):
    finished = pyqtSignal(QPixmap, str)  # emits (pixmap, base64 string)
    error = pyqtSignal(str)

    def __init__(self, name, cached_b64=None):
        super().__init__()
        self.name = name
        self.cached_b64 = cached_b64

    def run(self):
        pixmap = QPixmap()

        # Load from base64 if available
        if self.cached_b64:
            try:
                pixmap.loadFromData(base64.b64decode(self.cached_b64))
                self.finished.emit(pixmap, self.cached_b64)
                return
            except Exception as e:
                self.error.emit(f"Invalid cached base64: {e}")
                return

        # Else fetch from remote
        try:
            response = requests.get(
                f"https://crafthead.net/bust/{self.name}", timeout=5)
            response.raise_for_status()

            bust_bytes = response.content
            bust_b64 = base64.b64encode(bust_bytes).decode()
            pixmap.loadFromData(bust_bytes)

            self.finished.emit(pixmap, bust_b64)
        except Exception as e:
            self.error.emit(f"Failed to load bust for {self.name}: {e}")
