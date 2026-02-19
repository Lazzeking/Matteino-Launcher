# main.py
import os
import sys

# Ensure project root is on path so "from src.common import ..." works
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtWidgets import QApplication
from src.common import config as common_config
from src.common import paths as common_paths
from windows.main_window import UserLauncher

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = common_config.load_config("user")
    paths = common_config.get_user_paths("user")
    launcher = UserLauncher(config=cfg, paths=paths)
    launcher.show()
    sys.exit(app.exec())
