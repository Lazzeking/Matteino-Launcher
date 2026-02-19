# workers/versions_loader_worker.py
# Loads Minecraft version list in a background thread (mod_loader 8+).
# Loader versions (NeoForge/Forge/Fabric/Quilt) are fetched per MC version via mod_loader in the UI.

import minecraft_launcher_lib
from PyQt6.QtCore import QObject, pyqtSignal


class VersionsLoaderWorker(QObject):
    """Fetches Minecraft release versions only. Loader versions are loaded on demand via mod_loader."""
    finished = pyqtSignal(object, object, object)  # (all_forge, all_fabric, mc_release_ids) - first two unused for compat
    error = pyqtSignal(str)

    def run(self):
        mc_release = []
        try:
            mc_versions = minecraft_launcher_lib.utils.get_available_versions(
                minecraft_launcher_lib.utils.get_minecraft_directory()
            )
            mc_release = [v["id"] for v in mc_versions if v["type"] == "release"]
        except Exception as e:
            self.error.emit(str(e))
        self.finished.emit([], [], mc_release)
