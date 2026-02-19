import os
from PyQt6.QtCore import QObject, pyqtSignal
import minecraft_launcher_lib


def _loader_id_from_pack(loader_key: str) -> str:
    """Map pack dependency key to mod_loader id: neoforge, forge, fabric-loader -> fabric, quilt."""
    if loader_key == "fabric-loader":
        return "fabric"
    return loader_key  # neoforge, forge, quilt


class MCModLoaderInstallerWorker(QObject):
    """Installs Minecraft + mod loader (NeoForge, Forge, Fabric, Quilt) using mod_loader API (minecraft-launcher-lib 8+)."""
    finished = pyqtSignal(str)  # emits version_id for get_minecraft_command
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    progress_update_max = pyqtSignal(int)

    def __init__(self, base_dir: str, mc_version: str, loader_id: str, loader_version: str):
        super().__init__()
        self.base_dir = base_dir
        self.mc_version = mc_version
        self.loader_id = _loader_id_from_pack(loader_id)  # neoforge, forge, fabric, quilt
        self.loader_version = loader_version
        self.cancel_requested = False

    def make_install_callbacks(self, stage: str = ""):
        def set_status(text):
            self.status_update.emit(f"{stage}{text}")

        def set_progress(value):
            self.progress_update.emit(value)

        def set_max(value):
            self.progress_update_max.emit(value)

        return {
            "setStatus": set_status,
            "setProgress": set_progress,
            "setMax": set_max,
        }

    def run(self):
        os.makedirs(self.base_dir, exist_ok=True)
        try:
            # Vanilla first
            minecraft_launcher_lib.install.install_minecraft_version(
                self.mc_version,
                self.base_dir,
                self.make_install_callbacks("[MINECRAFT]"),
            )
            # Mod loader via unified mod_loader API
            loader = minecraft_launcher_lib.mod_loader.get_mod_loader(self.loader_id)
            loader.install(
                self.mc_version,
                self.base_dir,
                loader_version=self.loader_version,
                callback=self.make_install_callbacks(f"[{self.loader_id.upper()}]"),
            )
            version_id = loader.get_installed_version(self.mc_version, self.loader_version)
            self.finished.emit(version_id)
        except Exception as e:
            self.error.emit(str(e))
