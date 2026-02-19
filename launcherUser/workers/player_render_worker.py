from PyQt6.QtCore import QObject, pyqtSignal
import requests
from PyQt6.QtGui import QPixmap


class PlayerRenderWorker(QObject):
    finished = pyqtSignal(QPixmap)
    error = pyqtSignal(str)

    def __init__(self, player_name, parent=None):
        super().__init__(parent)
        self.player_name = player_name

    def run(self):
        import random
        player_render_types = [
            "default", "marching", "walking", "crouching", "crossed", "criss_cross", "ultimate", "cheering", "relaxing",
            "trudging", "cowering", "pointing", "lunging", "dungeons", "facepalm", "sleeping", "dead", "archer",
            "reading", "clown"
        ]

        selected_type = random.choice(player_render_types)
        try:
            url = f"https://starlightskins.lunareclipse.studio/render/{selected_type}/{self.player_name}/full"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            pixmap = QPixmap()
            pixmap.loadFromData(response.content)

            self.finished.emit(pixmap)
        except Exception as e:
            self.error.emit(str(e))
