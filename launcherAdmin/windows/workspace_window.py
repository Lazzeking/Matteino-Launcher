# windows/workspace_window.py

from datetime import datetime
import hashlib
from io import BytesIO
import os
import sys
from glob import glob
import json
import re
import shutil
import tempfile
import zipfile
import requests

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QPushButton, QPlainTextEdit, QScrollArea,
    QFileDialog, QMessageBox, QTabWidget, QFormLayout, QGridLayout, QGroupBox, QFrame, QDialog, QInputDialog, QSpinBox,
    QTableWidget, QTableWidgetItem, QCheckBox, QAbstractItemView, QHeaderView, QProgressDialog
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QThread, QProcess
import minecraft_launcher_lib

from src.common.version import __version__ as LAUNCHER_VERSION
from src.common.about_dialog import AboutDialog
from src.common import config as common_config
from src.common import translations as common_translations
from widgets.mod_entry_widget import ModEntryWidget
from workers.versions_loader_worker import VersionsLoaderWorker
from widgets.dependency_selection_dialog import DependencySelectionDialog
from widgets.log_window import LogWindow
from widgets.mod_search_dialog import ModSearchDialog
from widgets.optional_feature_dialog import OptionalFeatureDialog
from workers.bulk_import_worker import BulkImportWorker
from workers.install_worker import MrPackInstaller
from utils.patterns import collect_all_patterns, is_url


class WorkspaceWindow(QMainWindow):
    def __init__(self, workspace_path: str, icon_path=None, config=None):
        super().__init__()
        self.config = config or {}
        if icon_path and os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # When frozen, images_dir is next to exe; workspace is opened from selection window which has paths
            from src.common import paths as common_paths
            w = common_paths.writable_dir()
            fallback = os.path.join(w, "launcherAdmin", "resources", "images", "matteinocraft_mc_logo.png")
            if os.path.isfile(fallback):
                self.setWindowIcon(QIcon(fallback))

        self.workspace_path = workspace_path
        self._icon_path = icon_path
        self.setWindowTitle(
            self.tr("Workspace Management: {name}").format(name=os.path.basename(workspace_path)))
        self.setMinimumSize(1000, 700)

        self.suppress_success_messages = False
        self.current_pack_data = {}
        self._versions_signals_connected = False
        self._closing = False
        self._icon_threads = []  # icon fetch threads; we quit/wait in closeEvent

        # === Central Widget + Layout ===
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)

        # === Pack Selector Bar ===
        self.pack_selector = QComboBox()
        self.pack_selector.currentIndexChanged.connect(self.load_selected_pack)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel(self.tr("Select Pack:")))
        selector_layout.addWidget(self.pack_selector)

        reload_btn = QPushButton(self.tr("↻ Reload"))
        reload_btn.setFixedWidth(100)
        reload_btn.setToolTip(
            self.tr("Reloads the pack directly from the JSON"))
        reload_btn.clicked.connect(self.reload_selected_pack)
        selector_layout.addWidget(reload_btn)

        # === Test Pack Button ===
        test_pack_btn = QPushButton(self.tr("Test pack"))
        test_pack_btn.setFixedWidth(100)
        test_pack_btn.setToolTip(
            self.tr("Runs the modpack as a test instance")
        )
        test_pack_btn.clicked.connect(self.test_selected_pack)
        selector_layout.addWidget(test_pack_btn)

        # === Release Pack Button ===
        release_btn = QPushButton(self.tr("Release pack"))
        release_btn.setFixedWidth(100)
        release_btn.setToolTip(self.tr("Prepare files for server release"))
        release_btn.clicked.connect(self.release_pack)
        selector_layout.addWidget(release_btn)

        # === Open Folder Button ===
        open_folder_btn = QPushButton(self.tr("Open Folder"))
        open_folder_btn.setFixedWidth(120)
        open_folder_btn.setToolTip(self.tr("Open the pack's workspace folder"))
        open_folder_btn.clicked.connect(self.open_workspace_folder)
        selector_layout.addWidget(open_folder_btn)

        # === Add Pack Button ===
        add_pack_btn = QPushButton(self.tr("+ Add Pack"))
        add_pack_btn.setFixedWidth(100)
        add_pack_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;  /* Green */
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_pack_btn.setToolTip(self.tr("Create a new modpack"))
        add_pack_btn.clicked.connect(self.add_new_pack)
        selector_layout.addWidget(add_pack_btn)

        # === Remove Pack Button ===
        remove_pack_btn = QPushButton(self.tr("- Remove"))
        remove_pack_btn.setFixedWidth(100)
        remove_pack_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;  /* Green */
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        remove_pack_btn.setToolTip(self.tr("Remove the selected modpack"))
        remove_pack_btn.clicked.connect(self.remove_current_pack)
        selector_layout.addWidget(remove_pack_btn)

        # Launcher version (click to open About / credits and licenses)
        version_btn = QPushButton(self.tr("Launcher v{0}").format(LAUNCHER_VERSION))
        version_btn.setFlat(True)
        version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        version_btn.setStyleSheet("color: #fff; border: none; background: none;")
        version_btn.clicked.connect(self.show_about)
        selector_layout.addWidget(version_btn)

        main_layout.addLayout(selector_layout)

        # === Tabs ===
        self.tabs = QTabWidget()
        self.tab_pack_info = QWidget()
        self.tab_mods = QWidget()
        self.tab_overrides = QWidget()
        self.tab_optional_features = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_pack_info, self.tr("Pack Info"))
        self.tabs.addTab(self.tab_mods, self.tr("Mods"))
        self.tabs.addTab(self.tab_overrides, self.tr("Overrides"))
        self.tabs.addTab(self.tab_optional_features,
                         self.tr("Optional features"))
        self.tabs.addTab(self.tab_settings, self.tr("Settings"))
        self.tabs.setTabEnabled(1, False)  # Index 1 = Mods
        main_layout.addWidget(self.tabs)

        # === Tab Content ===
        self.setup_pack_info_tab()
        self.setup_mods_tab()
        self.setup_overrides_tab()
        self.setup_optional_features_tab()
        self.setup_settings_tab()

        # === Load Data ===
        self.load_loaders()
        self.load_available_packs()
        # Defer heavy API calls (Forge/Fabric/MC versions) so the window appears immediately
        self._start_versions_load()

    def save_override_paths(self):
        text = self.overrides_editor.toPlainText()
        paths = [line.strip() for line in text.splitlines() if line.strip()]
        self.current_pack_data["overrides"] = paths

        pack_file = os.path.join(
            self.workspace_path, f"{self.pack_selector.currentText()}.json")
        with open(pack_file, "w") as f:
            json.dump(self.current_pack_data, f, indent=4)

        QMessageBox.information(self, self.tr("Saved"), self.tr(
            "Override paths saved successfully."))

    def show_about(self):
        dialog = AboutDialog(
            parent=self,
            launcher_name=self.tr("Matteino Launcher Admin"),
            icon_path=self._icon_path,
        )
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.exec()

    def open_workspace_folder(self):
        current_pack = self.pack_selector.currentText()
        if not current_pack:
            return

        folder_path = os.path.join(self.workspace_path)
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, self.tr("Folder Not Found"),
                                self.tr("No folder found for {current_pack}").format(current_pack=current_pack))
            return

        # Open folder
        if os.name == 'nt':
            os.startfile(folder_path)
        elif os.name == 'posix':
            os.system(f'xdg-open "{folder_path}"')
        elif os.name == 'mac':
            os.system(f'open "{folder_path}"')

    def release_pack(self):
        def get_file_info(path):
            with open(path, "rb") as f:
                content = f.read()
                sha1 = hashlib.sha1(content).hexdigest()
                sha512 = hashlib.sha512(content).hexdigest()
                size = len(content)
            return {
                "sha1": sha1,
                "sha512": sha512,
                "size": size
            }

        current_pack_name = self.pack_selector.currentText()
        pack_path = os.path.join(
            self.workspace_path, f"{current_pack_name}.json")

        if not os.path.exists(pack_path):
            QMessageBox.warning(self, self.tr("Error"),
                                self.tr("Modpack JSON not found."))
            return

        with open(pack_path, "r") as f:
            pack_data = json.load(f)

        # Generate new versionId
        default_version_id = f"{pack_data.get('id', 'pack')}{datetime.now().strftime('%Y%m%d%H%M%S')}"

        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr("Release pack"))
        dialog.setLabelText(self.tr("Enter version ID:"))
        dialog.setTextValue(default_version_id)
        dialog.resize(400, 100)  # Set desired width and height
        ok = dialog.exec()

        version_id = dialog.textValue()

        if not ok or not version_id.strip():
            return

        version_id = version_id.strip()

        # Update and save pack file
        pack_data["versionId"] = version_id
        with open(pack_path, "w") as f:
            json.dump(pack_data, f, indent=4)

        # Remove useless entries
        del pack_data["settings"]

        # Create release folder (dist/)
        dist_path = os.path.join(self.workspace_path, "dist")
        dist_pack_path = os.path.join(dist_path, pack_data["id"])
        os.makedirs(dist_pack_path, exist_ok=True)

        # Copy overrides to dist
        base_override_folder = os.path.join(
            self.workspace_path, pack_data.get("id", "unknown"))

        # Normalize user patterns to be recursive if they end with '/*'
        normalized_patterns = collect_all_patterns(
            pack_data,
            os.path.join(self.workspace_path, base_override_folder)
        )

        overrides_files = []

        for pattern_entry in normalized_patterns:
            pattern = pattern_entry["source"]
            custom_target = pattern_entry.get("target")
            if is_url(pattern):
                try:
                    response = requests.get(pattern)
                    response.raise_for_status()
                    content = response.content
                    filename = os.path.basename(pattern.split("?")[0])
                    dest_path = os.path.join(dist_pack_path, filename)

                    with open(dest_path, "wb") as f:
                        f.write(content)

                    hashes = {
                        "sha1": hashlib.sha1(content).hexdigest(),
                        "sha512": hashlib.sha512(content).hexdigest(),
                        "size": len(content)
                    }

                    overrides_files.append({
                        "path": filename,
                        **hashes
                    })

                except Exception as e:
                    print(
                        f"Failed to download remote override: {pattern}, error: {e}")
                continue

            full_pattern = os.path.join(base_override_folder, pattern)
            for filepath in glob(full_pattern, recursive=True):
                if not os.path.isfile(filepath):
                    continue

                relative_path = os.path.relpath(filepath, base_override_folder)
                if custom_target:
                    relative_path = os.path.join(
                        custom_target, os.path.basename(relative_path))

                dest_path = os.path.join(dist_pack_path, relative_path)

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(filepath, dest_path)

                hashes = get_file_info(filepath)
                overrides_files.append({
                    "path": relative_path.replace("\\", "/"),
                    "sha1": hashes["sha1"],
                    "sha512": hashes["sha512"],
                    "size": hashes["size"]
                })

        pack_data["overridesFiles"] = overrides_files

        # === Update packages.json ===
        packages_path = os.path.join(dist_path, "packages.json")

        # Load existing packages.json if exists
        if os.path.exists(packages_path):
            with open(packages_path, "r") as f:
                try:
                    packages_data = json.load(f)
                except Exception:
                    packages_data = {"packages": []}
        else:
            packages_data = {"packages": []}

        # Replace or insert the released pack
        released_id = self.current_pack_data["id"]
        new_entry = {
            "name": released_id,
            "title": self.current_pack_data.get("name", released_id),
            "versionId": version_id,
            "priority": 0,
            "location": f"{released_id}.json"
        }

        updated = False
        for i, entry in enumerate(packages_data["packages"]):
            if entry["name"] == released_id:
                packages_data["packages"][i] = new_entry
                updated = True
                break

        if not updated:
            packages_data["packages"].append(new_entry)

        # Save packages.json
        with open(packages_path, "w") as f:
            json.dump(packages_data, f, indent=4)

        # Save JSON in release folder
        output_json_path = os.path.join(dist_path, f"{pack_data['id']}.json")
        with open(output_json_path, "w") as f:
            json.dump(pack_data, f, indent=4)

        # Open the release folder in file explorer
        QMessageBox.information(self, self.tr("Pack Released"),
                                self.tr("Pack released to:\n{dist_path}").format(dist_path=dist_path))
        os.startfile(dist_path) if os.name == 'nt' else os.system(
            f'open "{dist_path}"')

    def create_mrpack_file(self, pack_data: dict, output_path: str):
        """
        Crea un file .mrpack a partire dal dizionario pack_data (inclusi file override).
        """

        # === 1. Crea modrinth.index.json ===
        original_deps = pack_data.get("dependencies", {})
        mc_version = original_deps.get("minecraft", "")
        modrinth_deps = {}

        for key, value in original_deps.items():
            if key in ("forge", "neoforge") and isinstance(value, str) and value.startswith(f"{mc_version}-"):
                modrinth_deps[key] = value[len(mc_version) + 1:]
            else:
                modrinth_deps[key] = value

        manifest = {
            "formatVersion": 1,
            "game": "minecraft",
            "versionId": "{packname}-{dt}".format(
                packname=pack_data.get("name", "modpack"),
                dt=datetime.now().strftime("%Y%m%d%H%M%S")
            ),
            "name": pack_data.get("name", "Unnamed Modpack"),
            "summary": pack_data.get("summary", "A custom modpack"),
            "files": [],
            "dependencies": modrinth_deps
        }

        for mod in pack_data.get("files", []):
            if not mod.get("downloads"):
                continue
            manifest["files"].append({
                "path": mod.get("path", ""),
                "downloads": mod["downloads"],
                "fileSize": mod.get("fileSize", 0),
                "hashes": {
                    "sha1": mod.get("hashes", {}).get("sha1", ""),
                    "sha512": mod.get("hashes", {}).get("sha512", "")
                }
            })

        # === 2. Crea ZIP in memoria ===
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Write modrinth.index.json
            zipf.writestr("modrinth.index.json",
                          json.dumps(manifest, indent=4))

            base_override_folder = pack_data.get("id", "unknown")

            normalized_patterns = collect_all_patterns(
                pack_data,
                os.path.join(self.workspace_path, base_override_folder)
            )

            for pattern_entry in normalized_patterns:
                pattern = pattern_entry["source"]
                custom_target = pattern_entry.get("target")
                if is_url(pattern):
                    try:
                        response = requests.get(pattern)
                        response.raise_for_status()
                        content = response.content
                        filename = os.path.basename(pattern.split("?")[0])
                        if custom_target:
                            override_path_in_zip = os.path.join(
                                "overrides", custom_target, os.path.basename(relative_path))
                        else:
                            override_path_in_zip = os.path.join(
                                "overrides", relative_path)

                        print(
                            f"Adding remote file: {pattern} -> {override_path_in_zip}")
                        zipf.writestr(override_path_in_zip, content)
                    except Exception as e:
                        print(
                            f"[ERROR] Failed to download remote file: {pattern} — {e}")
                    continue  # Skip to next pattern

                # Handle as local glob
                if not any(char in pattern for char in ['*', '?']):
                    pattern = os.path.join(pattern, '**')

                full_pattern = os.path.join(
                    self.workspace_path, base_override_folder, pattern)
                print(f"Checking pattern: {full_pattern}")

                top_level_folder = os.path.normpath(
                    base_override_folder).split(os.sep)[0]
                for file_path in glob(full_pattern, recursive=True):
                    if not os.path.isfile(file_path):
                        print(f"Not a file: {file_path}")
                        continue

                    relative_path = os.path.relpath(file_path, os.path.join(
                        self.workspace_path, top_level_folder))
                    override_path_in_zip = os.path.join(
                        "overrides", relative_path)

                    print(f"Adding: {file_path} as {override_path_in_zip}")
                    zipf.write(file_path, override_path_in_zip)

        # === 3. Salva il file .mrpack ===
        with open(output_path, "wb") as f:
            f.write(zip_buffer.getvalue())

    def launch_minecraft(self, minecraft_directory, modpack_directory, mrpack_path):
        settings = self.current_pack_data.get("settings", {})

        options = minecraft_launcher_lib.utils.generate_test_options()
        options["gameDirectory"] = modpack_directory

        min_ram = int(settings.get('min_ram', 2048))
        max_ram = int(settings.get('max_ram', 4096))

        options["jvmArguments"] = [
            f"-Xms{min_ram}M",
            f"-Xmx{max_ram}M"
        ] + settings.get('jvm_args', '').split()

        options["javaPath"] = settings.get("java_path", "")
        command = minecraft_launcher_lib.command.get_minecraft_command(
            minecraft_launcher_lib.mrpack.get_mrpack_launch_version(mrpack_path), minecraft_directory, options)

        self.log_window.start_process(command[1:])

    def cancel_test_process(self):
        # === Cancel install thread if it's still active ===
        install_thread = getattr(self, "install_thread", None)
        if install_thread is not None:
            try:
                if install_thread.isRunning():
                    install_thread.requestInterruption()
                    install_thread.quit()
                    install_thread.wait()
            except RuntimeError:
                print("Install thread was already deleted.")

        # === Kill Minecraft process if it's running ===
        if hasattr(self, "log_window") and hasattr(self.log_window, "process"):
            process = self.log_window.process
            if process and process.state() != QProcess.ProcessState.NotRunning:
                print(self.tr("Terminating Minecraft process..."))
                process.kill()

        # Optionally close the log window
        if hasattr(self, "log_window") and self.log_window.isVisible():
            self.log_window.close()

    def test_selected_pack(self):
        current_pack_name = self.pack_selector.currentText()
        pack_path = os.path.join(
            self.workspace_path, f"{current_pack_name}.json")

        if not os.path.exists(pack_path):
            QMessageBox.warning(self, self.tr("Error"), self.tr("Pack JSON file not found."))
            return

        with open(pack_path, "r") as f:
            pack_data = json.load(f)

        mrpack_output = os.path.join(
            self.workspace_path, f"{current_pack_name}.mrpack")
        try:
            self.create_mrpack_file(pack_data, mrpack_output)
            QMessageBox.information(
                self, self.tr("Success"), self.tr("Created: {path}").format(path=mrpack_output))

            try:
                mrpack_information = minecraft_launcher_lib.mrpack.get_mrpack_information(
                    mrpack_output)
            except Exception:
                print(f"{mrpack_output} is not a valid .mrpack File")
                return

            minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()

            modpack_directory = os.path.join(
                self.workspace_path, "_testInstance")
            os.makedirs(modpack_directory, 511, True)

            # Adds the Optional Files
            mrpack_install_options: minecraft_launcher_lib.types.MrpackInstallOptions = {
                "optionalFiles": []}
            for i in mrpack_information["optionalFiles"]:
                confirm = QMessageBox.question(
                    self,
                    self.tr("Optional files"),
                    self.tr(
                        "The Pack includes the Optional File {i}.\nDo you want to install it?".format(i=i)),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if confirm == QMessageBox.StandardButton.Yes:
                    mrpack_install_options["optionalFiles"].append(i)

            # Create log window and show it early
            # Pass empty args, not launching Java yet
            self.log_window = LogWindow(parent=self)
            self.log_window.canceled.connect(self.cancel_test_process)
            self.log_window.show()

            self.install_thread = QThread()
            self.installer = MrPackInstaller(
                mrpack_output, minecraft_directory, modpack_directory, mrpack_install_options)

            self.installer.moveToThread(self.install_thread)
            self.install_thread.started.connect(self.installer.run)

            self.installer.status_update.connect(self.log_window.set_status)
            self.installer.progress_update.connect(
                self.log_window.set_progress)
            self.installer.set_max_progress.connect(
                self.log_window.set_max_progress)

            self.installer.finished.connect(self.install_thread.quit)
            self.installer.finished.connect(self.install_thread.deleteLater)
            self.installer.finished.connect(lambda: self.launch_minecraft(
                minecraft_directory, modpack_directory, mrpack_output))  # Launch after install
            self.install_thread.start()

        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"), self.tr("Error while creating the .mrpack file:\n{e}").format(e=e))

    def reload_selected_pack(self):
        confirm = QMessageBox.question(
            self,
            self.tr("Reload pack"),
            self.tr(
                "Are you sure about reload the JSON file?\nUnsaved changes will be lost."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.load_selected_pack()

    def add_new_pack(self):
        pack_name, ok = QInputDialog.getText(
            self, self.tr("New Modpack"), self.tr("Enter a name for the new modpack:"))
        if ok and pack_name:
            filename = f"{pack_name}.json"
            path = os.path.join(self.workspace_path, filename)

            if os.path.exists(path):
                QMessageBox.warning(self, self.tr("Already Exists"),
                                    self.tr("A modpack with this name already exists."))
                return

            empty_pack = {
                "id": pack_name,
                "files": [],
                "dependencies": {
                    "minecraft": ""
                }
            }

            with open(path, "w") as f:
                json.dump(empty_pack, f, indent=4)

            os.makedirs(os.path.join(
                self.workspace_path, pack_name), 511, True)

            self.pack_selector.addItem(pack_name)
            self.pack_selector.setCurrentText(pack_name)
            self.load_selected_pack()

    def remove_current_pack(self):
        current_pack = self.pack_selector.currentText()
        if not current_pack:
            return

        confirm = QMessageBox.question(
            self,
            self.tr("Delete Modpack"),
            self.tr("Are you sure you want to delete '{current_pack}'?").format(
                current_pack=current_pack),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            path = os.path.join(self.workspace_path, f"{current_pack}.json")
            try:
                os.remove(path)
                os.removedirs(os.path.join(self.workspace_path, current_pack))
            except Exception as e:
                QMessageBox.critical(
                    self, self.tr("Error"), self.tr("Could not delete modpack: {e}").format(e=e))
                return

            self.pack_selector.removeItem(self.pack_selector.currentIndex())
            if self.pack_selector.count() > 0:
                self.load_selected_pack()
            else:
                self.current_pack_data = {}
                self.render_mod_list()

    def check_versions_selected(self):
        mc_ok = bool(self.mc_version_selector.currentText().strip())
        loader_sel = self.loader_selector.currentText().strip().lower()
        if loader_sel in ("neoforge", "forge"):
            loader_ok = bool(self.forge_version_selector.currentText().strip())
        elif loader_sel in ("fabric-loader", "quilt"):
            loader_ok = bool(self.fabric_version_selector.currentText().strip())
        else:
            loader_ok = False
        # Mods tab available as soon as we have pack data from disk, or when version dropdowns are set
        has_mod_list = bool(self.current_pack_data.get("files"))
        self.tabs.setTabEnabled(1, has_mod_list or (mc_ok and loader_ok))

    def setup_pack_info_tab(self):
        layout = QFormLayout()

        # === Fields ===
        self.name_field = QLineEdit()

        self.summary_field = QLineEdit()

        self.mc_version_selector = QComboBox()
        self.mc_version_selector.setEditable(True)
        self.mc_version_selector.lineEdit().setReadOnly(True)
        self.mc_version_selector.setMaxVisibleItems(10)

        self.loader_selector = QComboBox()
        self.loader_selector.setEditable(True)
        self.loader_selector.lineEdit().setReadOnly(True)
        self.loader_selector.setMaxVisibleItems(10)

        self.forge_version_selector = QComboBox()
        self.forge_version_selector.setEditable(True)
        self.forge_version_selector.lineEdit().setReadOnly(True)
        self.forge_version_selector.setMaxVisibleItems(10)

        self.forge_version_label = QLabel(self.tr("Loader version:"))

        self.fabric_version_selector = QComboBox()
        self.fabric_version_selector.setEditable(True)
        self.fabric_version_selector.lineEdit().setReadOnly(True)
        self.fabric_version_selector.setMaxVisibleItems(10)

        self.fabric_version_label = QLabel(self.tr("Fabric version:"))

        self.forge_version_label.hide()
        self.fabric_version_label.hide()
        self.forge_version_selector.hide()
        self.fabric_version_selector.hide()

        # === Save Button ===
        self.save_info_button = QPushButton(self.tr("Save Changes"))
        self.save_info_button.clicked.connect(self.save_pack_info)

        # === Add to layout ===

        layout.addRow(self.tr("Pack name:"), self.name_field)
        layout.addRow(self.tr("Summary:"), self.summary_field)
        layout.addRow(self.tr("Minecraft version:"), self.mc_version_selector)
        layout.addRow(self.tr("Loader:"), self.loader_selector)
        layout.addRow(self.forge_version_label, self.forge_version_selector)
        layout.addRow(self.fabric_version_label, self.fabric_version_selector)
        layout.addRow(self.save_info_button)

        # === Apply layout ===
        self.tab_pack_info.setLayout(layout)

    def setup_mods_tab(self):
        layout = QVBoxLayout()
        self.tab_mods.setLayout(layout)

        # Add mod via URL
        add_mod_layout = QHBoxLayout()
        self.add_mod_url = QLineEdit()
        self.add_mod_url.setPlaceholderText(
            self.tr("Paste Modrinth or CurseForge mod URL...")
        )
        self.add_mod_button = QPushButton(self.tr("Add mod"))
        self.add_mod_button.clicked.connect(self.handle_add_mod)
        self.add_mod_bulk_button = QPushButton(self.tr("Add mods..."))
        self.add_mod_bulk_button.clicked.connect(self.handle_add_mod_bulk)
        self.search_mods_button = QPushButton(self.tr("Search mods"))
        self.search_mods_button.clicked.connect(self.open_mod_search_dialog)
        self.check_deps_button = QPushButton(self.tr("Check dependencies"))
        self.check_deps_button.clicked.connect(self.handle_check_dependencies)
        self.mod_count_label = QLabel(self.tr("Mods: {n}").format(n=0))

        add_mod_layout.addWidget(self.add_mod_url)
        add_mod_layout.addWidget(self.add_mod_button)
        add_mod_layout.addWidget(self.add_mod_bulk_button)
        add_mod_layout.addWidget(self.search_mods_button)
        add_mod_layout.addWidget(self.check_deps_button)
        add_mod_layout.addWidget(self.mod_count_label)

        layout.addLayout(add_mod_layout)

        # Filter and sort installed mods
        filter_sort_row = QHBoxLayout()
        filter_sort_row.addWidget(QLabel(self.tr("Filter:")))
        self.mod_filter_input = QLineEdit()
        self.mod_filter_input.setPlaceholderText(
            self.tr("Filter by name or description...")
        )
        self.mod_filter_input.textChanged.connect(self._apply_mod_list_filter)
        filter_sort_row.addWidget(self.mod_filter_input)
        filter_sort_row.addWidget(QLabel(self.tr("Sort by:")))
        self.mod_sort_combo = QComboBox()
        self.mod_sort_combo.addItem(self.tr("Name (A–Z)"), "name_asc")
        self.mod_sort_combo.addItem(self.tr("Name (Z–A)"), "name_desc")
        self.mod_sort_combo.addItem(self.tr("Source (Modrinth first)"), "source_modrinth")
        self.mod_sort_combo.addItem(self.tr("Source (CurseForge first)"), "source_curseforge")
        self.mod_sort_combo.addItem(self.tr("Project ID (A–Z)"), "project_asc")
        self.mod_sort_combo.addItem(self.tr("Project ID (Z–A)"), "project_desc")
        self.mod_sort_combo.currentIndexChanged.connect(self._reorder_mod_list)
        filter_sort_row.addWidget(self.mod_sort_combo)
        filter_sort_row.addStretch()
        layout.addLayout(filter_sort_row)

        # Scrollable mod list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.mod_list_widget = QWidget()
        self.mod_list_layout = QVBoxLayout()
        self.mod_list_widget.setLayout(self.mod_list_layout)
        self._mod_entry_widgets = []  # refs for filtering

        self.scroll_area.setWidget(self.mod_list_widget)
        layout.addWidget(self.scroll_area)

    def select_java_path(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Select Java Executable"))
        if path:
            self.java_path_input.setText(path)

    def setup_overrides_tab(self):
        layout = QVBoxLayout()

        self.overrides_editor = QPlainTextEdit()
        self.overrides_editor.setPlaceholderText(self.tr(
            "Enter one override path per line.\nYou can optionally specify a custom target path:\n\nExamples:\n  config/*\n  resourcepacks/example.zip => custompacks/example.zip"))
        layout.addWidget(QLabel(self.tr("Override paths:")))
        layout.addWidget(self.overrides_editor)

        save_button = QPushButton(self.tr("Save Overrides"))
        save_button.clicked.connect(self.save_override_paths)
        layout.addWidget(save_button)

        self.tab_overrides.setLayout(layout)

    def setup_optional_features_tab(self):
        layout = QVBoxLayout()

        self.optional_features_table = QTableWidget(0, 7)
        self.optional_features_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.optional_features_table.horizontalHeader().setStretchLastSection(True)
        self.optional_features_table.horizontalHeader(
        ).setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.optional_features_table.setWordWrap(True)
        self.optional_features_table.setHorizontalHeaderLabels([
            self.tr("Name"), self.tr("Description"), self.tr("Recommendation"),
            self.tr("Default?"), self.tr("Source"), self.tr("Target"), self.tr("Type")
        ])
        self.optional_features_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.optional_features_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton(self.tr("Add"))
        edit_btn = QPushButton(self.tr("Edit"))
        remove_btn = QPushButton(self.tr("Remove"))

        add_btn.clicked.connect(self.add_optional_feature)
        edit_btn.clicked.connect(self.edit_optional_feature)
        remove_btn.clicked.connect(self.remove_optional_feature)

        for btn in (add_btn, edit_btn, remove_btn):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        self.tab_optional_features.setLayout(layout)

    def refresh_optional_features_table(self):
        features = self.current_pack_data.get("optionalFeatures", [])
        self.optional_features_table.setRowCount(0)

        for feature in features:
            includes = feature.get("include", [])
            remotes = feature.get("remote", [])

            # Combine all into one list with unified format
            rows = []

            for inc in includes:
                if isinstance(inc, str):
                    src, tgt = inc, inc
                else:
                    src = inc.get("source", "")
                    tgt = inc.get("target", src)
                rows.append((self.tr("Local"), src, tgt))

            for rem in remotes:
                src = rem.get("url", "")
                tgt = rem.get("target", "")
                rows.append((self.tr("Remote"), src, tgt))

            # Create a row in the table for each file entry
            for typ, src, tgt in rows:
                row = self.optional_features_table.rowCount()
                self.optional_features_table.insertRow(row)

                self.optional_features_table.setItem(
                    row, 0, QTableWidgetItem(feature.get("name", "")))
                self.optional_features_table.setItem(
                    row, 1, QTableWidgetItem(feature.get("description", "")))
                self.optional_features_table.setItem(
                    row, 2, QTableWidgetItem(feature.get("recommendation", "normal")))

                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsUserCheckable |
                               Qt.ItemFlag.ItemIsEnabled)
                check.setCheckState(Qt.CheckState.Checked if feature.get(
                    "selectedByDefault") else Qt.CheckState.Unchecked)
                self.optional_features_table.setItem(row, 3, check)

                self.optional_features_table.setItem(
                    row, 4, QTableWidgetItem(src))
                self.optional_features_table.setItem(
                    row, 5, QTableWidgetItem(tgt or ""))
                self.optional_features_table.setItem(
                    row, 6, QTableWidgetItem(typ))

        self.optional_features_table.resizeRowsToContents()

    def add_optional_feature(self):
        dlg = OptionalFeatureDialog(parent=self)
        if dlg.exec():
            feature = dlg.get_feature()
            self.current_pack_data.setdefault(
                "optionalFeatures", []).append(feature)
            self.refresh_optional_features_table()
            self.save_optional_features()

    def edit_optional_feature(self):
        row = self.optional_features_table.currentRow()
        if row < 0:
            return
        features = self.current_pack_data.get("optionalFeatures", [])
        feature = features[row]
        dlg = OptionalFeatureDialog(feature, parent=self)
        if dlg.exec():
            features[row] = dlg.get_feature()
            self.refresh_optional_features_table()
            self.save_optional_features()

    def remove_optional_feature(self):
        row = self.optional_features_table.currentRow()
        if row < 0:
            return
        del self.current_pack_data["optionalFeatures"][row]
        self.refresh_optional_features_table()
        self.save_optional_features()

    def save_optional_features(self):
        pack_file = os.path.join(
            self.workspace_path, f"{self.pack_selector.currentText()}.json")
        with open(pack_file, "w") as f:
            json.dump(self.current_pack_data, f, indent=4)

    def setup_settings_tab(self):
        layout = QFormLayout()
        self.tab_settings.setLayout(layout)

        # === RAM Settings ===
        self.min_ram_input = QSpinBox()
        self.min_ram_input.setRange(512, 16384)
        self.min_ram_input.setSuffix(self.tr(" MB"))
        self.min_ram_input.setValue(2048)

        self.max_ram_input = QSpinBox()
        self.max_ram_input.setRange(512, 16384)
        self.max_ram_input.setSuffix(self.tr(" MB"))
        self.max_ram_input.setValue(4096)

        # === Java Path ===
        self.java_path_input = QLineEdit()
        java_path_btn = QPushButton(self.tr("Browse"))
        java_path_btn.clicked.connect(self.select_java_path)
        java_path_layout = QHBoxLayout()
        java_path_layout.addWidget(self.java_path_input)
        java_path_layout.addWidget(java_path_btn)

        # === JVM Args ===
        self.jvm_args_input = QLineEdit()

        # === Language (launcher UI) ===
        self._language_choices = common_translations.get_available_languages("admin")
        current_file = common_translations.get_current_translation_file(self.config)
        self.language_combo = QComboBox()
        self.language_combo.blockSignals(True)
        for i, choice in enumerate(self._language_choices):
            self.language_combo.addItem(choice["name"], choice)
            if choice["file"] == current_file:
                self.language_combo.setCurrentIndex(i)
        self.language_combo.blockSignals(False)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        layout.addRow(self.tr("Language:"), self.language_combo)

        # === Save Button ===
        save_btn = QPushButton(self.tr("Save Settings"))
        save_btn.clicked.connect(self.save_launcher_settings)

        # === Add to Layout ===
        layout.addRow(self.tr("Min RAM:"), self.min_ram_input)
        layout.addRow(self.tr("Max RAM:"), self.max_ram_input)
        layout.addRow(self.tr("Java Path:"), java_path_layout)
        layout.addRow(self.tr("JVM Args:"), self.jvm_args_input)
        layout.addRow(save_btn)

    def save_launcher_settings(self):
        if not hasattr(self, "current_pack_data"):
            QMessageBox.warning(
                self, self.tr("No Pack"), self.tr("No modpack is currently loaded."))
            return

        self.current_pack_data["settings"] = {
            "min_ram": self.min_ram_input.value(),
            "max_ram": self.max_ram_input.value(),
            "java_path": self.java_path_input.text().strip(),
            "jvm_args": self.jvm_args_input.text().strip()
        }

        pack_file = os.path.join(
            self.workspace_path, f"{self.pack_selector.currentText()}.json")
        with open(pack_file, "w") as f:
            json.dump(self.current_pack_data, f, indent=4)

        QMessageBox.information(self, self.tr("Settings Saved"),
                                self.tr("Launcher settings saved successfully."))

    def _on_language_changed(self, index: int):
        if index < 0 or index >= len(self._language_choices):
            return
        choice = self._language_choices[index]
        if choice["id"] == "":
            trans = {"enabled": False, "file": "", "locale": "en"}
        else:
            trans = {"enabled": True, "file": choice["file"], "locale": choice["id"]}
        common_config.save_user_config("admin", {"translations": trans})
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def save_pack_info(self):
        name = self.name_field.text().strip()
        summary = self.summary_field.text().strip()
        mc_version = self.mc_version_selector.currentText().strip()
        loader = self.loader_selector.currentText().strip().lower()

        if loader in ("neoforge", "forge"):
            loader_version = self.forge_version_selector.currentText().strip()
        elif loader in ("fabric-loader", "quilt"):
            loader_version = self.fabric_version_selector.currentText().strip()
        else:
            loader_version = ""

        if not name or not mc_version or not loader or not loader_version:
            QMessageBox.warning(
                self, self.tr("Missing infos"), self.tr("Fill in all required fields (Name, MC version, Loader and Loader version)"))
            return

        # Update data
        self.current_pack_data["name"] = name
        self.current_pack_data["summary"] = summary
        self.current_pack_data["dependencies"] = {
            "minecraft": mc_version,
            loader: loader_version  # neoforge, forge, fabric-loader, or quilt
        }

        # Save to JSON
        pack_file = os.path.join(
            self.workspace_path,
            f"{self.pack_selector.currentText()}.json"
        )

        try:
            with open(pack_file, "w") as f:
                json.dump(self.current_pack_data, f, indent=4)

            QMessageBox.information(
                self, self.tr("Saved"), self.tr("Pack saved successfully."))

            # Enable Mods tab (if valid) and switch if needed
            self.check_versions_selected()
            if self.tabs.isTabEnabled(1):
                self.tabs.setCurrentIndex(1)

        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"), self.tr("Cannot save the file: {e}").format(e=e))

    def load_available_packs(self):
        self.pack_selector.clear()
        json_files = glob(os.path.join(self.workspace_path, "*.json"))
        pack_names = [os.path.splitext(os.path.basename(f))[
            0] for f in json_files]
        self.pack_selector.addItems(pack_names)
        # Load first pack from disk immediately so Mods tab is available without waiting for APIs
        if self.pack_selector.count() > 0:
            self.load_selected_pack()

    def load_selected_pack(self):
        pack_name = self.pack_selector.currentText()
        if not pack_name:
            return

        pack_file = os.path.join(self.workspace_path, f"{pack_name}.json")
        if not os.path.exists(pack_file):
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Pack file not found."))
            return

        with open(pack_file, "r") as f:
            self.current_pack_data = json.load(f)

        settings = self.current_pack_data.get("settings", {})
        # Fill overrides editor
        override_paths = self.current_pack_data.get("overrides", [])
        self.overrides_editor.setPlainText("\n".join(override_paths))

        self.min_ram_input.setValue(settings.get("min_ram", 2048))
        self.max_ram_input.setValue(settings.get("max_ram", 4096))
        self.java_path_input.setText(settings.get("java_path", ""))
        self.jvm_args_input.setText(settings.get("jvm_args", ""))

        # ✅ Fill pack info tab fields
        self.name_field.setText(self.current_pack_data.get("name", ""))
        self.summary_field.setText(
            self.current_pack_data.get("summary", ""))

        deps = self.current_pack_data.get("dependencies", {})
        mc_version = deps.get("minecraft", "").strip()
        # Support neoforge, forge (legacy "1.20.1-47.3.12" or "47.3.12"), fabric-loader, quilt
        selected_loader = ""
        loader_version_value = ""
        for key in ("neoforge", "forge", "fabric-loader", "quilt"):
            raw = deps.get(key, "").strip()
            if not raw:
                continue
            selected_loader = key
            if key in ("forge", "neoforge") and "-" in raw and raw.startswith(mc_version + "-"):
                loader_version_value = raw[len(mc_version) + 1 :].strip()
            else:
                loader_version_value = raw
            break

        index = self.mc_version_selector.findText(mc_version)
        if index != -1:
            self.mc_version_selector.setCurrentIndex(index)

        if selected_loader:
            loader_index = self.loader_selector.findText(selected_loader)
            if loader_index != -1:
                self.loader_selector.setCurrentIndex(loader_index)
            self._fill_loader_version_combo()
            if selected_loader in ("neoforge", "forge"):
                combo = self.forge_version_selector
            else:
                combo = self.fabric_version_selector
            i = combo.findText(loader_version_value)
            if i != -1:
                combo.setCurrentIndex(i)
            elif loader_version_value:
                # Pack has version but it's not in the list (e.g. API failed or old format): add it so Mods tab can enable
                combo.insertItem(0, loader_version_value)
                combo.setCurrentIndex(0)

        # Render mod list
        self.render_mod_list()
        self.check_versions_selected()
        # Refresh optional features table
        self.refresh_optional_features_table()
        # Switch to Mods tab if MC and loader version are selected
        mc_version = self.mc_version_selector.currentText().strip()
        loader_sel = self.loader_selector.currentText().strip().lower()
        lv = (self.forge_version_selector if loader_sel in ("neoforge", "forge") else self.fabric_version_selector).currentText().strip()
        if mc_version and loader_sel and lv:
            self.tabs.setCurrentIndex(1)

    def edit_mod_placeholder(self, mod):
        QMessageBox.information(
            self, self.tr("Edit"), self.tr("Edit placeholder for: {mod_title}").format(mod_title=mod.get('title')))

    def remove_mod(self, mod):
        project_id_to_remove = mod.get("project_id")
        all_mods = self.current_pack_data.get("files", [])

        # Step 1: Find dependents of this mod
        dependent_mods = [
            m for m in all_mods
            if any(dep.get("project_id") == project_id_to_remove for dep in m.get("dependencies", []))
        ]

        # Step 2: If no dependents, just confirm removal
        if not dependent_mods:
            confirm = QMessageBox.question(
                self,
                self.tr("Remove mod"),
                self.tr("Vuoi rimuovere la mod '{mod_title}'?").format(
                    mod_title=mod.get("title")),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            all_mods = [m for m in all_mods if m != mod]

        else:
            # Prompt with choice
            dependents_names = "\n".join(
                "- {mod_title}".format(mod_title=m.get('title', self.tr('Unknown'))) for m in dependent_mods)
            msg = (
                self.tr("Other mods depend on '{mod_title}'. You want to remove them too?:\n\n").format(
                    mod_title=mod.get('title')),
                self.tr("Yes. You will remove these mods:\n{dependents_names}\n\n").format(
                    dependents_names=dependents_names),
                self.tr("No. You will remove only this mod\n"),
                self.tr("Cancel. Cancel the removal\n"),
                self.tr("Choose an option:")
            )

            remove_all = QMessageBox.question(
                self,
                self.tr("Mods removal with dependents"),
                " ".join(msg),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )

            if remove_all == QMessageBox.StandardButton.Cancel:
                return
            elif remove_all == QMessageBox.StandardButton.No:
                # Remove only the selected mod
                all_mods = [m for m in all_mods if m != mod]
            elif remove_all == QMessageBox.StandardButton.Yes:
                # Recursive removal
                to_remove_ids = {project_id_to_remove}
                changed = True
                while changed:
                    changed = False
                    for m in all_mods:
                        if m.get("project_id") in to_remove_ids:
                            continue
                        for dep in m.get("dependencies", []):
                            if dep.get("project_id") in to_remove_ids:
                                to_remove_ids.add(m.get("project_id"))
                                changed = True
                all_mods = [m for m in all_mods if m.get(
                    "project_id") not in to_remove_ids]

                QMessageBox.information(
                    self, self.tr("Mods removed"), self.tr("Removal complete"))

        # Update list
        self.current_pack_data["files"] = all_mods

        # Save
        pack_file = os.path.join(
            self.workspace_path, f"{self.pack_selector.currentText()}.json")
        with open(pack_file, "w") as f:
            json.dump(self.current_pack_data, f, indent=4)

        self.render_mod_list()

    def _check_missing_hard_dependencies(self):
        """
        Scan current pack mods and return mods that have required (hard) dependencies
        not installed. Only considers Modrinth mods (with project_id and dependencies list).
        Returns list of {"mod": mod_entry, "missing": [{"name", "project_id", "url"}, ...]}.
        """
        files = self.current_pack_data.get("files", [])
        installed_ids = {m.get("project_id") for m in files if m.get("project_id")}
        result = []
        for mod in files:
            deps = mod.get("dependencies", [])
            required = [d for d in deps if d.get("type") == "required" and d.get("project_id")]
            if not required:
                continue
            missing = [
                {"name": d.get("name", d.get("project_id", "?")), "project_id": d.get("project_id"), "url": d.get("url", "")}
                for d in required
                if d.get("project_id") not in installed_ids
            ]
            if missing:
                result.append({"mod": mod, "missing": missing})
        return result

    def _resolve_missing_deps_for_install(self, issues):
        """
        From _check_missing_hard_dependencies result, build unique missing project_ids,
        fetch compatible Modrinth versions (pack's mc_version + Modrinth loader id), and return
        list of mod infos for DependencySelectionDialog / handle_modrinth_url: each
        {"title", "slug", "project_id", "url", "icon_url", "version_number", ...}.
        Returns (list of resolved mods, list of unresolved {name, project_id, url}).
        """
        deps_cfg = self.current_pack_data.get("dependencies", {})
        mc_version, modrinth_loader = self._get_pack_modrinth_loader(deps_cfg)
        if not mc_version or not modrinth_loader:
            return [], []

        # Unique missing project_ids (keep first name/url we saw)
        missing_by_id = {}
        for item in issues:
            for dep in item["missing"]:
                pid = dep.get("project_id")
                if pid and pid not in missing_by_id:
                    missing_by_id[pid] = {"name": dep.get("name", pid), "url": dep.get("url", "")}

        resolved = []
        unresolved = []
        for project_id, info in missing_by_id.items():
            try:
                project_data = requests.get(
                    f"https://api.modrinth.com/v2/project/{project_id}").json()
                versions = requests.get(
                    f"https://api.modrinth.com/v2/project/{project_id}/version").json()
                compatible = [
                    v for v in versions
                    if mc_version in v.get("game_versions", []) and modrinth_loader in v.get("loaders", [])
                ]
                if not compatible:
                    unresolved.append({"name": project_data.get("title", info["name"]), "project_id": project_id, "url": f"https://modrinth.com/mod/{project_data.get('slug', '') or project_id}"})
                    continue
                v = compatible[0]
                resolved.append({
                    "title": project_data.get("title", info["name"]),
                    "description": project_data.get("description", ""),
                    "slug": project_data.get("slug", ""),
                    "project_id": project_id,
                    "url": f"https://modrinth.com/mod/{project_data.get('slug')}",
                    "icon_url": project_data.get("icon_url", ""),
                    "dependency_type": "required",
                    "version_number": v.get("version_number", ""),
                })
            except Exception as e:
                print(f"Failed to resolve dependency {project_id}: {e}")
                unresolved.append({"name": info.get("name", project_id), "project_id": project_id, "url": info.get("url", "")})
        return resolved, unresolved

    def handle_check_dependencies(self):
        """Check for missing hard dependencies; resolve compatible mods and offer to install them."""
        issues = self._check_missing_hard_dependencies()
        if not issues:
            QMessageBox.information(
                self,
                self.tr("Dependencies check"),
                self.tr("All mods have their required dependencies installed."),
            )
            return
        deps_cfg = self.current_pack_data.get("dependencies", {})
        mc_version, modrinth_loader = self._get_pack_modrinth_loader(deps_cfg)
        if not mc_version or not modrinth_loader:
            QMessageBox.warning(
                self,
                self.tr("Dependencies check"),
                self.tr("Set Minecraft version and mod loader in Pack Info first, then run Check dependencies again."),
            )
            return
        resolved, unresolved = self._resolve_missing_deps_for_install(issues)
        if not resolved and not unresolved:
            return
        if not resolved:
            # All missing deps could not be resolved (no compatible version)
            msg = self.tr("Missing required dependencies could not be resolved for your Minecraft/loader. Add them manually from Modrinth:\n\n")
            msg += "\n".join(f"• {u.get('name', u.get('project_id'))}" for u in unresolved)
            QMessageBox.warning(self, self.tr("Missing dependencies"), msg)
            return
        # Show dialog: these mods will be added when you click OK (same as add-mod dependency flow)
        already_added = {
            m.get("project_id") for m in self.current_pack_data.get("files", [])
            if m.get("project_id")
        }
        dlg = DependencySelectionDialog(
            resolved,
            [],
            unresolved_required=unresolved,
            unresolved_optional=[],
            parent_mod={"title": self.tr("Missing required dependencies (will be added)")},
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for dep_mod in resolved:
            if dep_mod.get("project_id") in already_added:
                continue
            self.handle_modrinth_url(
                f"https://modrinth.com/mod/{dep_mod['slug']}",
                already_added=already_added,
            )
            already_added.add(dep_mod.get("project_id"))
        self.render_mod_list()
        QMessageBox.information(
            self,
            self.tr("Dependencies check"),
            self.tr("Missing required dependencies have been added. Run Check dependencies again if you have many levels of deps."),
        )

    def start_bulk_import(self, file_path):
        self.progress_dialog = QProgressDialog(
            self.tr("Importing mods..."), self.tr("Cancel"), 0, 100, self
        )
        self.progress_dialog.setWindowTitle(self.tr("Bulk Import"))
        self.progress_dialog.setWindowModality(
            Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)  # Show immediately

        # Setup worker + thread
        self.thread = QThread()
        self.worker = BulkImportWorker(
            file_path, handler=self)  # pass self as handler
        self.worker.moveToThread(self.thread)

        # Connect worker signals
        self.worker.progress_changed.connect(self.progress_dialog.setValue)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.progress_dialog.close)
        self.worker.error.connect(
            lambda msg: QMessageBox.critical(self, self.tr("Error"), msg))
        self.progress_dialog.canceled.connect(self.worker.stop)

        # Thread lifecycle
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start process
        self.thread.start()
        self.progress_dialog.exec()

    def handle_add_mod_bulk(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select bulk file"), "")
        if not file_path:
            return
        self.start_bulk_import(file_path)

    def open_mod_search_dialog(self):
        """Open the search mods modal (Modrinth / CurseForge) and add selected mods to the pack."""
        deps = self.current_pack_data.get("dependencies", {})
        mc_version, modrinth_loader = self._get_pack_modrinth_loader(deps)
        curseforge_key = (self.config.get("curseforge_api_key") or "").strip()

        # Set of (provider, project_id) for mods already in the pack (so search can show "Already installed")
        installed_ids = set()
        for mod in self.current_pack_data.get("files", []):
            pid = mod.get("project_id")
            if not pid:
                continue
            pid = str(pid)
            url = mod.get("url", "") or ""
            if "modrinth.com" in url:
                installed_ids.add(("modrinth", pid))
            elif "curseforge.com" in url or "forgecdn.net" in "".join(mod.get("downloads", [])):
                installed_ids.add(("curseforge", pid))

        def on_add_mod(hit: dict):
            url = hit.get("url", "")
            if hit.get("provider") == "modrinth":
                self.handle_modrinth_url(url)
            elif hit.get("provider") == "curseforge":
                self.handle_curseforge_url(url)
            self.render_mod_list()

        dialog = ModSearchDialog(
            parent=self,
            game_version=mc_version,
            loader=modrinth_loader,
            curseforge_api_key=curseforge_key,
            on_add_mod=on_add_mod,
            installed_mod_ids=installed_ids,
        )
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.exec()

    def handle_add_mod(self):
        url = self.add_mod_url.text().strip()
        if not url:
            return

        if "modrinth.com" in url:
            self.handle_modrinth_url(url)
        elif "curseforge.com" in url:
            self.handle_curseforge_url(url)
        else:
            QMessageBox.warning(self, self.tr("Unsupported URL"),
                                self.tr("Only MODRINTH and CURSEFORGE are supported."))

        self.add_mod_url.setText("")

    def handle_modrinth_url(self, url: str, already_added: set[str] = None):
        bulk_mode = hasattr(self, "_bulk_dependency_queue")

        if already_added is None:
            already_added = {
                mod.get("project_id") for mod in self.current_pack_data.get("files", [])
                if mod.get("project_id")
            }

        try:
            deps = self.current_pack_data.get("dependencies", {})
            mc_version, modrinth_loader = self._get_pack_modrinth_loader(deps)

            if not mc_version:
                if not bulk_mode:
                    QMessageBox.warning(
                        self, self.tr("Minecraft version missing"), self.tr("You need to select a Minecraft version first."))
                return
            if not modrinth_loader:
                if not bulk_mode:
                    QMessageBox.warning(
                        self, self.tr("Mod loader missing"), self.tr("You need to select a mod loader (NeoForge, Forge, Fabric, or Quilt) in Pack Info first."))
                return

            parts = url.strip("/").split("/")

            version_data = None
            project_data = None
            project_id = None

            # CASE 1: Direct CDN
            if "cdn.modrinth.com" in url:
                if len(parts) < 7:
                    raise ValueError(self.tr("Invalid CDN URL."))
                project_id = parts[4]
                if project_id in already_added:
                    print(f"Skipping already-added CDN mod: {project_id}")
                    return
                version_id = parts[6]
                version_data = requests.get(
                    f"https://api.modrinth.com/v2/version/{version_id}").json()
                project_data = requests.get(
                    f"https://api.modrinth.com/v2/project/{project_id}").json()

            # CASE 2: Version page
            elif "modrinth.com" in url and "version" in parts:
                version_id = parts[6]
                version_data = requests.get(
                    f"https://api.modrinth.com/v2/version/{version_id}").json()
                project_id = version_data["project_id"]
                if project_id in already_added:
                    print(f"Skipping already-added version mod: {project_id}")
                    return
                project_data = requests.get(
                    f"https://api.modrinth.com/v2/project/{project_id}").json()

            # CASE 3: Project page
            elif "modrinth.com" in url and "mod" in parts:
                slug = parts[4]
                project_data = requests.get(
                    f"https://api.modrinth.com/v2/project/{slug}").json()
                project_id = project_data["id"]
                if project_id in already_added:
                    print(f"Skipping already-added slug mod: {project_id}")
                    return
                versions = requests.get(
                    f"https://api.modrinth.com/v2/project/{project_id}/version").json()
                compatible_versions = [
                    v for v in versions
                    if mc_version in v.get("game_versions", []) and modrinth_loader in v.get("loaders", [])
                ]
                if not compatible_versions:
                    raise ValueError(
                        self.tr("No compatible version found for Minecraft {mc_version} and {loader}.").format(mc_version=mc_version, loader=modrinth_loader))
                version_data = compatible_versions[0]
            else:
                raise ValueError(self.tr("Unrecognized Modrinth URL."))

            already_added.add(project_id)

            # Dependencies (Modrinth): resolve compatible versions and track unresolved
            required_mods = []
            optional_mods = []
            unresolved_required = []
            unresolved_optional = []
            for dep in version_data.get("dependencies", []):
                if not dep.get("project_id"):
                    continue
                dep_type = dep.get("dependency_type", "required")
                try:
                    dep_project = requests.get(
                        f"https://api.modrinth.com/v2/project/{dep['project_id']}").json()
                    dep_versions = requests.get(
                        f"https://api.modrinth.com/v2/project/{dep['project_id']}/version"
                    ).json()
                    compatible = [
                        v for v in dep_versions
                        if mc_version in v.get("game_versions", []) and modrinth_loader in v.get("loaders", [])
                    ]
                    minimal_info = {
                        "title": dep_project.get("title", dep["project_id"]),
                        "project_id": dep["project_id"],
                        "slug": dep_project.get("slug", ""),
                        "url": f"https://modrinth.com/mod/{dep_project.get('slug', '') or dep['project_id']}",
                    }
                    if not compatible:
                        if dep_type == "required":
                            unresolved_required.append(minimal_info)
                        else:
                            unresolved_optional.append(minimal_info)
                        continue
                    dep_version = compatible[0]
                    dep_info = {
                        "title": dep_project.get("title", dep["project_id"]),
                        "description": dep_project.get("description", ""),
                        "slug": dep_project.get("slug"),
                        "project_id": dep["project_id"],
                        "url": f"https://modrinth.com/mod/{dep_project.get('slug')}",
                        "icon_url": dep_project.get("icon_url", ""),
                        "dependency_type": dep_type,
                        "version_number": dep_version.get("version_number", "")
                    }
                    if dep_type == "required":
                        required_mods.append(dep_info)
                    else:
                        optional_mods.append(dep_info)
                except Exception as e:
                    print(
                        f"Failed to fetch dependency info for {dep['project_id']}: {e}")
                    minimal_info = {
                        "title": dep.get("project_id", "?"),
                        "project_id": dep.get("project_id", ""),
                        "url": f"https://modrinth.com/project/{dep.get('project_id', '')}",
                    }
                    if dep_type == "required":
                        unresolved_required.append(minimal_info)
                    else:
                        unresolved_optional.append(minimal_info)

            required_mods = [
                m for m in required_mods if m["project_id"] not in already_added]
            optional_mods = [
                m for m in optional_mods if m["project_id"] not in already_added]

            # Always show dependency dialog when the mod has any deps (so user must add resolvable ones)
            has_any_deps = required_mods or optional_mods or unresolved_required or unresolved_optional
            if has_any_deps:
                if bulk_mode:
                    self._bulk_dependency_queue.extend(
                        f"https://modrinth.com/mod/{dep_mod['slug']}"
                        for dep_mod in required_mods + optional_mods
                    )
                else:
                    dlg = DependencySelectionDialog(
                        required_mods, optional_mods,
                        unresolved_required=unresolved_required,
                        unresolved_optional=unresolved_optional,
                        parent_mod={"title": project_data.get(
                            "title"), "slug": project_data.get("slug")},
                        parent=self
                    )
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        return
                    selected_optional_mods = dlg.get_selected_optional_mods()
                    for dep_mod in required_mods + selected_optional_mods:
                        self.handle_modrinth_url(
                            f"https://modrinth.com/mod/{dep_mod['slug']}", already_added=already_added
                        )

            # Build deps list
            readable_deps = []
            for dep in version_data.get("dependencies", []):
                if not dep.get("project_id"):
                    continue
                try:
                    dep_project = requests.get(
                        f"https://api.modrinth.com/v2/project/{dep['project_id']}").json()
                    readable_deps.append({
                        "name": dep_project.get("title", dep["project_id"]),
                        "type": dep.get("dependency_type", "required"),
                        "slug": dep_project.get("slug"),
                        "project_id": dep['project_id'],
                        "url": f"https://modrinth.com/mod/{dep_project.get('slug')}"
                    })
                except Exception:
                    readable_deps.append({
                        "name": dep["project_id"],
                        "type": dep.get("dependency_type", "required"),
                        "project_id": dep["project_id"]
                    })

            file_info = version_data['files'][0]
            mod_entry = {
                "title": project_data.get("title", self.tr("Unknown mod")),
                "description": project_data.get("description", ""),
                "url": f"https://modrinth.com/mod/{project_data.get('slug')}",
                "icon_url": project_data.get("icon_url", ""),
                "path": f"mods/{file_info['filename']}",
                "downloads": [f["url"] for f in version_data["files"]],
                "hashes": file_info.get("hashes", {}),
                "fileSize": file_info.get("size", 0),
                "env": version_data.get("environment", {}),
                "dependencies": readable_deps,
                "project_id": project_id,
                "version_number": version_data.get("version_number", "")
            }

            self.current_pack_data.setdefault("files", []).append(mod_entry)
            pack_file = os.path.join(
                self.workspace_path, f"{self.pack_selector.currentText()}.json")
            with open(pack_file, "w") as f:
                json.dump(self.current_pack_data, f, indent=4)

            self.render_mod_list()
            if not bulk_mode and not self.suppress_success_messages:
                QMessageBox.information(
                    self, self.tr("Success"), self.tr("Mod '{title}' added successfully.").format(title=mod_entry['title']))

        except Exception as e:
            if not bulk_mode:
                QMessageBox.critical(
                    self, self.tr("Error"), self.tr("Error while adding mod from Modrinth:\n{e}").format(e=e))
            else:
                print(f"[Bulk] Modrinth error: {e}")

    def _curseforge_url_for_dep(self, dep: dict) -> str:
        """Return CurseForge mod page URL for a dependency dict (from API: url/slug, or fallback name as id)."""
        url = (dep.get("url") or "").strip()
        if url and "curseforge.com" in url:
            return url
        slug = dep.get("slug") or dep.get("name") or ""
        return f"https://www.curseforge.com/minecraft/mc-mods/{slug}"

    def _curseforge_dep_info_from_mod_id(
        self, mod_id: int, dep_type: str, headers: dict, api_base: str
    ) -> dict:
        """Fetch CurseForge mod by ID and return dep_info with title, slug, url for dialog and adding."""
        fallback = {
            "name": str(mod_id),
            "title": str(mod_id),
            "slug": "",
            "url": "",
            "project_id": str(mod_id),
            "type": dep_type,
        }
        try:
            r = requests.get(f"{api_base}/mods/{mod_id}", headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json().get("data")
            if not data:
                return fallback
            links = data.get("links") or {}
            return {
                "name": data.get("slug", str(mod_id)),
                "title": data.get("name", str(mod_id)),
                "slug": data.get("slug", ""),
                "url": links.get("websiteUrl", ""),
                "project_id": str(data.get("id", mod_id)),
                "type": dep_type,
            }
        except Exception:
            return fallback

    def handle_curseforge_url(self, url: str, already_added: set[str] = None):
        bulk_mode = hasattr(self, "_bulk_dependency_queue")

        CURSEFORGE_API_KEY = (self.config.get("curseforge_api_key") or "").strip()
        if not CURSEFORGE_API_KEY:
            if not bulk_mode:
                QMessageBox.warning(
                    self,
                    self.tr("CurseForge API key missing"),
                    self.tr("Set curseforge_api_key in admin.config.json or LAUNCHER_CURSEFORGE_API_KEY in the environment to add mods from CurseForge."),
                )
            return
        CURSEFORGE_API_BASE = "https://api.curseforge.com/v1"
        GAME_ID = 432  # Minecraft

        if already_added is None:
            already_added = {
                mod.get("project_id") for mod in self.current_pack_data.get("files", [])
                if mod.get("project_id")
            }

        try:
            deps = self.current_pack_data.get("dependencies", {})
            mc_version = deps.get("minecraft", "").strip()

            if not mc_version:
                if not bulk_mode:
                    QMessageBox.warning(
                        self,
                        self.tr("Minecraft version missing"),
                        self.tr("You need to select a minecraft version first."),
                    )
                return

            headers = {"x-api-key": CURSEFORGE_API_KEY,
                       "Accept": "application/json"}

            # === Case 1: Direct ForgeCDN file link ===
            if "edge.forgecdn.net" in url:
                parts = url.split("/")
                if len(parts) < 7:
                    raise ValueError("Invalid ForgeCDN file URL")

                folder_id = parts[4]  # e.g. "5644"
                file_id = parts[5]  # e.g. "976"
                project_file_id = int(folder_id + file_id)  # e.g. "5644976"

                file_resp = requests.post(f"{CURSEFORGE_API_BASE}/mods/files",
                                          headers=headers, json={"fileIds": [project_file_id]})
                file_resp.raise_for_status()

                file_info = file_resp.json().get("data")[0]

                if not file_info:
                    raise ValueError("Project not found on Curseforge")

                project_id = file_info["modId"]

                print(f"Mod id found : {project_id}")

                project_resp = requests.get(
                    f"{CURSEFORGE_API_BASE}/mods/{project_id}", headers=headers)
                project_resp.raise_for_status()
                project = project_resp.json().get("data", [])

                # Get file list for this project
                files_url = f"{CURSEFORGE_API_BASE}/mods/{project_id}/files"
                files_resp = requests.get(files_url, headers=headers)
                files_resp.raise_for_status()
                all_files = files_resp.json().get("data", [])

                # Pick matching file (by file name in URL if you want exact match)
                filename_in_url = parts[6]
                matching_files = [
                    f for f in all_files if f["fileName"] == filename_in_url]
                if not matching_files:
                    # fallback: first file
                    latest_file = all_files[0]
                else:
                    latest_file = matching_files[0]

            # === Case 2: CurseForge mod page ===
            else:
                def extract_slug_from_url(url: str) -> str:
                    match = re.match(
                        r"https://www\.curseforge\.com/minecraft/mc-mods/([^/]+)", url)
                    if not match:
                        raise ValueError(self.tr("Invalid CurseForge mod URL"))
                    return match.group(1)

                slug = extract_slug_from_url(url)

                # Search mod by slug
                search_url = f"{CURSEFORGE_API_BASE}/mods/search"
                response = requests.get(search_url, headers=headers, params={
                    "gameId": GAME_ID, "slug": slug
                })
                response.raise_for_status()

                results = response.json().get("data", [])
                if not results and slug.isdigit():
                    # Slug is numeric (e.g. dependency shown as ID 326652); fetch mod by ID
                    by_id = requests.get(
                        f"{CURSEFORGE_API_BASE}/mods/{slug}", headers=headers, timeout=10
                    )
                    if by_id.ok:
                        project = by_id.json().get("data")
                        if project:
                            results = [project]
                if not results:
                    raise ValueError(self.tr("Curseforge mod not found"))
                project = results[0]
                project_id = project["id"]

                # Get all files
                files_url = f"{CURSEFORGE_API_BASE}/mods/{project_id}/files"
                files_resp = requests.get(files_url, headers=headers)
                files_resp.raise_for_status()
                all_files = files_resp.json().get("data", [])

                compatible_files = [
                    f for f in all_files
                    if mc_version in f.get("gameVersions", [])
                ]
                if not compatible_files:
                    raise ValueError(
                        self.tr("No file compatible with minecraft version {mc_version}."))

                latest_file = compatible_files[0]

            # === Early check ===
            if str(project_id) in already_added:
                print(f"Skipping already-added mod: {project_id}")
                return
            already_added.add(str(project_id))

            filename = latest_file["fileName"]
            file_url = latest_file["downloadUrl"]
            file_size = latest_file["fileLength"]
            file_hashes = latest_file.get("hashes", [])

            # === Format hashes ===
            hashes = {}
            for h in file_hashes:
                if h["algo"] == 1:
                    hashes["sha1"] = h["value"]
                elif h["algo"] == 3:
                    hashes["sha512"] = h["value"]

            if "sha512" not in hashes and file_url:
                try:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_path = tmp_file.name
                        with requests.get(file_url, stream=True) as r:
                            r.raise_for_status()
                            for chunk in r.iter_content(chunk_size=8192):
                                tmp_file.write(chunk)
                    sha512 = hashlib.sha512()
                    with open(tmp_path, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            sha512.update(chunk)
                    hashes["sha512"] = sha512.hexdigest()
                    os.remove(tmp_path)
                except Exception as e:
                    print(f"Error calculating SHA512: {e}")

            # === Dependencies ===
            required_mods = []
            optional_mods = []
            raw_deps = latest_file.get("dependencies", [])
            for dep in raw_deps:
                mod_id = dep["modId"]
                dep_type = "required" if dep["relationType"] == 3 else "optional"
                # Fetch mod by ID so we show name (e.g. "Cupboard") and have slug/url for adding
                dep_info = self._curseforge_dep_info_from_mod_id(
                    mod_id, dep_type, headers, CURSEFORGE_API_BASE
                )
                if dep_info["type"] == "required":
                    required_mods.append(dep_info)
                else:
                    optional_mods.append(dep_info)

            if required_mods or optional_mods:
                if bulk_mode:
                    self._bulk_dependency_queue.extend(
                        self._curseforge_url_for_dep(dep) for dep in required_mods + optional_mods
                    )
                else:
                    dlg = DependencySelectionDialog(
                        required_mods, optional_mods,
                        parent_mod={
                            "title": project["name"], "slug": project.get("slug", "")},
                        parent=self
                    )
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        return
                    selected_optional_mods = dlg.get_selected_optional_mods()
                    for dep_mod in required_mods + selected_optional_mods:
                        self.handle_curseforge_url(
                            self._curseforge_url_for_dep(dep_mod),
                            already_added=already_added
                        )

            # === Create mod entry ===
            mod_entry = {
                "title": project["name"],
                "description": project["summary"],
                "url": project["links"]["websiteUrl"],
                "icon_url": project.get("logo", {}).get("thumbnailUrl", ""),
                "path": f"mods/{filename}",
                "downloads": [file_url] if file_url else [],
                "hashes": hashes,
                "fileSize": file_size,
                "env": {"client": "required", "server": "optional"},
                "dependencies": required_mods + optional_mods,
                "project_id": str(project_id),
                "version_number": ""
            }

            self.current_pack_data.setdefault("files", []).append(mod_entry)

            # === Save back to disk ===
            pack_file = os.path.join(
                self.workspace_path, f"{self.pack_selector.currentText()}.json"
            )
            with open(pack_file, "w") as f:
                json.dump(self.current_pack_data, f, indent=4)

            self.render_mod_list()
            if not bulk_mode:
                QMessageBox.information(
                    self,
                    self.tr("Success"),
                    self.tr("Mod '{mod_title}' added successfully.").format(
                        mod_title=mod_entry['title']
                    )
                )

        except Exception as e:
            if not bulk_mode:
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr(
                        "Error encountered during the curseforge mod adding:\n{e}").format(e=e)
                )
            else:
                print(f"[Bulk] CurseForge error: {e}")

    def _apply_mod_list_filter(self):
        """Show only mod entries whose name or description matches the filter text."""
        q = (getattr(self, "mod_filter_input", None) and self.mod_filter_input.text() or "").strip().lower()
        for w in getattr(self, "_mod_entry_widgets", []):
            if not q:
                w.setVisible(True)
                continue
            data = getattr(w, "mod_data", {}) or {}
            title = (data.get("title") or "").lower()
            desc = (data.get("description") or "").lower()
            w.setVisible(q in title or q in desc)

    def _mod_sort_key(self, widget):
        """Return a sort key tuple for the given mod entry widget (by current sort combo)."""
        data = getattr(widget, "mod_data", {}) or {}
        sort_id = getattr(self, "mod_sort_combo", None) and self.mod_sort_combo.currentData() or "name_asc"
        title = (data.get("title") or "").lower()
        project_id = (data.get("project_id") or "").lower()
        url = data.get("url") or ""
        if "modrinth.com" in url:
            source_order = 0
        elif "curseforge.com" in url or "forgecdn.net" in "".join(data.get("downloads", [])):
            source_order = 1
        else:
            source_order = 2
        if sort_id == "name_asc":
            return (title,)
        if sort_id == "name_desc":
            return (title,)
        if sort_id == "source_modrinth":
            return (source_order, title)
        if sort_id == "source_curseforge":
            return (1 - source_order, title)  # CurseForge first
        if sort_id == "project_asc":
            return (project_id, title)
        if sort_id == "project_desc":
            return (project_id, title)
        return (title,)

    def _reorder_mod_list(self):
        """Reorder the mod list by the current sort combo; keeps existing widgets."""
        widgets = getattr(self, "_mod_entry_widgets", [])
        if not widgets:
            return
        sort_id = getattr(self, "mod_sort_combo", None) and self.mod_sort_combo.currentData() or "name_asc"
        reverse = sort_id in ("name_desc", "project_desc")
        widgets.sort(key=self._mod_sort_key)
        if reverse:
            widgets.reverse()
        # Remove all items from layout (widgets stay alive)
        while self.mod_list_layout.count():
            item = self.mod_list_layout.takeAt(0)
        for w in widgets:
            self.mod_list_layout.addWidget(w)
        self.mod_list_layout.addStretch()

    def render_mod_list(self):
        # Clear all items from layout — widgets and spacers
        self._mod_entry_widgets = []
        while self.mod_list_layout.count():
            item = self.mod_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Rebuild the mod list (icons loaded async, cached under workspace .launcher_cache/icons)
        mods = self.current_pack_data.get("files", [])
        self.mod_count_label.setText(self.tr("Mods: {n}").format(n=len(mods)))
        icon_cache_dir = os.path.join(self.workspace_path, ".launcher_cache", "icons")
        for mod in mods:
            widget = ModEntryWidget(
                mod,
                on_edit=self.edit_mod_placeholder,
                on_remove=self.remove_mod,
                icon_cache_dir=icon_cache_dir,
                icon_thread_registry=self,
            )
            self._mod_entry_widgets.append(widget)
            self.mod_list_layout.addWidget(widget)

        self.mod_list_layout.addStretch()
        self._reorder_mod_list()
        self._apply_mod_list_filter()

    def load_loaders(self):
        # Prefer NeoForge over Forge (mod_loader 8+)
        loaders = ["", "neoforge", "forge", "fabric-loader", "quilt"]
        self.loader_selector.addItems(loaders)
        self.loader_selector.currentIndexChanged.connect(
            self.on_loader_selected)

    def _start_versions_load(self):
        """Load Minecraft version list in background (only fills Pack Info dropdowns; Mods tab uses cached data)."""
        # Do not parent thread to self: closing the window must not destroy a running thread
        self._versions_thread = QThread()
        self._versions_worker = VersionsLoaderWorker()
        self._versions_worker.moveToThread(self._versions_thread)
        self._versions_thread.started.connect(self._versions_worker.run)
        self._versions_worker.finished.connect(self._on_versions_loaded)
        self._versions_worker.finished.connect(self._versions_thread.quit)
        self._versions_worker.error.connect(self._on_versions_error)
        self._versions_thread.finished.connect(self._versions_worker.deleteLater)
        self._versions_thread.finished.connect(self._versions_thread.deleteLater)
        self._versions_thread.start()

    def register_icon_thread(self, thread):
        """Track an icon-fetch thread so we can quit/wait on close."""
        self._icon_threads.append(thread)

    def unregister_icon_thread(self, thread):
        try:
            self._icon_threads.remove(thread)
        except ValueError:
            pass

    def closeEvent(self, event):
        """Quit versions and icon-fetch threads and wait so we don't destroy them while running."""
        self._closing = True
        if getattr(self, "_versions_worker", None):
            try:
                self._versions_worker.finished.disconnect(self._on_versions_loaded)
            except Exception:
                pass
        try:
            thread = getattr(self, "_versions_thread", None)
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(5000)
        except RuntimeError:
            pass
        # Quit and wait for icon fetch threads (avoid "Destroyed while thread is still running")
        for t in list(self._icon_threads):
            try:
                if t.isRunning():
                    t.quit()
                    t.wait(2000)
            except RuntimeError:
                pass
        self._icon_threads.clear()
        super().closeEvent(event)

    def _on_versions_error(self, msg: str):
        QMessageBox.critical(self, self.tr("Error"), msg)

    def _on_versions_loaded(self, _all_forge, _all_fabric, mc_release):
        """Apply Minecraft version list from background worker and refresh pack UI."""
        if self._closing:
            return
        self.mc_version_selector.addItems(mc_release or [])
        if not self._versions_signals_connected:
            self._versions_signals_connected = True
            self.mc_version_selector.currentIndexChanged.connect(self.on_mc_version_selected)
            self.forge_version_selector.currentIndexChanged.connect(self.check_versions_selected)
            self.fabric_version_selector.currentIndexChanged.connect(self.check_versions_selected)
        if self.pack_selector.currentText():
            self.load_selected_pack()

    def _mod_loader_id(self):
        """Current loader selector value -> mod_loader id (neoforge, forge, fabric, quilt)."""
        sel = self.loader_selector.currentText().strip().lower()
        return "fabric" if sel == "fabric-loader" else sel if sel else None

    def _get_pack_modrinth_loader(self, deps_cfg=None):
        """
        From pack dependencies, return (mc_version, modrinth_loader_id).
        modrinth_loader_id is the string Modrinth API uses in version['loaders']:
        'neoforge', 'forge', 'fabric', or 'quilt'. Pack stores loader *version* (e.g. neoforge: "1.20.1-47.3.12"),
        so we use which key is set, not the value.
        """
        if deps_cfg is None:
            deps_cfg = self.current_pack_data.get("dependencies", {})
        mc_version = (deps_cfg.get("minecraft") or "").strip()
        for key in ("neoforge", "forge", "fabric-loader", "quilt"):
            if (deps_cfg.get(key) or "").strip():
                loader_id = "fabric" if key == "fabric-loader" else key
                return mc_version, loader_id
        return mc_version, ""

    def _fill_loader_version_combo(self):
        """Fill the visible loader version combo via mod_loader for current MC version."""
        mc_version = self.mc_version_selector.currentText().strip()
        loader_id = self._mod_loader_id()
        if not mc_version or not loader_id:
            return
        try:
            loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
            versions = loader.get_loader_versions(mc_version, True)
            if self.loader_selector.currentText().strip().lower() in ("neoforge", "forge"):
                self.forge_version_selector.clear()
                self.forge_version_selector.addItems(versions or [])
            else:
                self.fabric_version_selector.clear()
                self.fabric_version_selector.addItems(versions or [])
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Error loading loader versions: {e}").format(e=e))

    def load_minecraft_versions(self):
        mc_versions = minecraft_launcher_lib.utils.get_available_versions(
            minecraft_launcher_lib.utils.get_minecraft_directory()
        )

        release_versions = [v["id"]
                            for v in mc_versions if v["type"] == "release"]

        self.mc_version_selector.addItems(release_versions)
        self.mc_version_selector.currentIndexChanged.connect(
            self.on_mc_version_selected)
        self.forge_version_selector.currentIndexChanged.connect(
            self.check_versions_selected)

        # Reload selected pack now that MC versions are loaded
        if self.pack_selector.currentText():
            self.load_selected_pack()

    def on_mc_version_selected(self):
        self._fill_loader_version_combo()
        self.check_versions_selected()

    def on_loader_selected(self):
        loader_selected = self.loader_selector.currentText().strip().lower()
        deps = self.current_pack_data.setdefault("dependencies", {})

        for key in ("neoforge", "forge", "fabric-loader", "quilt"):
            if key in deps:
                del deps[key]

        if loader_selected in ("neoforge", "forge"):
            self.forge_version_label.setText(
                self.tr("NeoForge version:") if loader_selected == "neoforge" else self.tr("Forge version:"))
            self.forge_version_label.show()
            self.forge_version_selector.show()
            self.fabric_version_label.hide()
            self.fabric_version_selector.hide()
            self._fill_loader_version_combo()
        elif loader_selected in ("fabric-loader", "quilt"):
            self.fabric_version_label.setText(
                self.tr("Fabric version:") if loader_selected == "fabric-loader" else self.tr("Quilt version:"))
            self.forge_version_label.hide()
            self.forge_version_selector.hide()
            self.fabric_version_label.show()
            self.fabric_version_selector.show()
            self._fill_loader_version_combo()
        else:
            self.forge_version_label.hide()
            self.forge_version_selector.hide()
            self.fabric_version_label.hide()
            self.fabric_version_selector.hide()
        self.check_versions_selected()
