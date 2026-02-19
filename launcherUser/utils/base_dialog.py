import os
from PyQt6.QtWidgets import QDialog
from PyQt6.QtGui import QIcon

from utils.base_stylesheet import getBaseStylesheet


class BaseDialog(QDialog):
    def __init__(self, parent=None, icon_path=None, **kwargs):
        super().__init__(parent, **kwargs)
        if icon_path:
            icon_file = os.path.join(icon_path, "matteinocraft_mc_logo.png") if os.path.isdir(icon_path) else icon_path
            if os.path.isfile(icon_file):
                self.setWindowIcon(QIcon(icon_file))
        else:
            fallback = "./resources/images/matteinocraft_mc_logo.png"
            if os.path.isfile(fallback):
                self.setWindowIcon(QIcon(fallback))
        self.setStyleSheet(getBaseStylesheet())
