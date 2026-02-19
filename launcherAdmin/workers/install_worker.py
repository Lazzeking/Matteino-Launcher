import os
import shutil
from PyQt6.QtCore import QObject, pyqtSignal
import minecraft_launcher_lib


class MrPackInstaller(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    set_max_progress = pyqtSignal(int)

    def __init__(self, mrpack_path, minecraft_dir, modpack_dir, install_options=None):
        super().__init__()
        self.mrpack_path = mrpack_path
        self.minecraft_dir = minecraft_dir
        self.modpack_dir = modpack_dir
        self.install_options = install_options or {}
        self.cancel_requested = False

    def run(self):

        callback = {
            "setStatus": lambda text: not self.cancel_requested and self.status_update.emit(text),
            "setProgress": lambda val: not self.cancel_requested and self.progress_update.emit(val),
            "setMax": lambda max_val: not self.cancel_requested and self.set_max_progress.emit(max_val)
        }
        if os.path.exists(self.modpack_dir):
            shutil.rmtree(self.modpack_dir)
        os.makedirs(self.modpack_dir, exist_ok=True)

        try:
            minecraft_launcher_lib.mrpack.install_mrpack(
                self.mrpack_path,
                self.minecraft_dir,
                modpack_directory=self.modpack_dir,
                mrpack_install_options=self.install_options,
                callback=callback
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
