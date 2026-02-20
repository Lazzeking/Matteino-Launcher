import os
import sys

# Ensure project root is on path so "from src.common import ..." works
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtCore import QTranslator, QLocale, QLibraryInfo
from PyQt6.QtWidgets import QApplication
from src.common import config as common_config
from src.common import paths as common_paths
from windows.workspace_selection_window import WorkspaceSelectionWindow


def main():
    app = QApplication(sys.argv)
    cfg = common_config.load_config("admin")
    paths = common_config.get_user_paths("admin")

    # Optional translation from config
    trans_cfg = cfg.get("translations", {})
    if trans_cfg.get("enabled"):
        translator = QTranslator()
        trans_file = trans_cfg.get("file", "launcherAdmin/translations/it.qm")
        if not os.path.isabs(trans_file):
            root = common_paths.base_dir() if getattr(sys, "frozen", False) else _project_root
            trans_file = os.path.join(root, trans_file)
        if os.path.isfile(trans_file):
            translator.load(trans_file)
            app.installTranslator(translator)

    window = WorkspaceSelectionWindow(config=cfg, paths=paths)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
