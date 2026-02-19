import os
import json
import shutil
import requests
import hashlib
from urllib.parse import urljoin
from PyQt6.QtCore import QObject, pyqtSignal


class UpdateModpackWorker(QObject):
    finished = pyqtSignal(dict, str)  # emits (pack_index, base_dir)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, pack_info, package_base, selected_optional_features=None, packs_dir=None):
        super().__init__()
        self.pack_info = pack_info
        self.package_base = package_base
        self.selected_optional_features = selected_optional_features or []
        self.packs_dir = packs_dir or "packs"
        self.cancel_requested = False

    def log(self, msg: str):
        self.status_update.emit(msg)

    def file_matches(self, path, expected_sha512):
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            return hashlib.sha512(f.read()).hexdigest() == expected_sha512

    def download_file(self, url, dest_path):
        try:
            r = requests.get(url, stream=True)
            r.raise_for_status()
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        except Exception as e:
            self.log(
                f"<b style='color:red;'>Failed to download {url}: {e}</b>")

    def run(self):
        index_url = urljoin(self.package_base + "/",
                            self.pack_info["location"])
        try:
            self.log(f"Fetching index from: {index_url}")
            response = requests.get(index_url)
            response.raise_for_status()
            pack_index = response.json()
        except Exception as e:
            self.error.emit(f"Failed to fetch index: {e}")
            return

        base_dir = os.path.join(self.packs_dir, self.pack_info["name"])
        os.makedirs(base_dir, exist_ok=True)

        # === MOD FILES ===
        for file in pack_index.get("files", []):
            if self.cancel_requested:
                return

            path = os.path.join(base_dir, file["path"])
            expected_hash = file["hashes"].get("sha512")

            if not self.file_matches(path, expected_hash):
                self.log(f"Downloading mod: {file['title']} → {file['path']}")
                self.download_file(file["downloads"][0], path)
            else:
                self.log(f"✓ {file['title']} is up to date.")

        # === OVERRIDES FILES ===
        for override in pack_index.get("overridesFiles", []):
            if self.cancel_requested:
                return

            path = os.path.join(base_dir, override["path"])
            url = f"{self.package_base}/{pack_index['id']}/{override['path']}"
            expected_hash = override["sha512"]

            if not self.file_matches(path, expected_hash):
                self.log(f"Downloading override: {override['path']}")
                self.download_file(url, path)
            else:
                self.log(f"✓ Override up to date: {override['path']}")

        # === OPTIONAL FEATURES ===
        for feature in pack_index.get("optionalFeatures", []):
            name = feature.get("name")

            match = next(
                (item for item in self.selected_optional_features if item["name"] == name), None)

            if match is not None:
                if not match.get("selected"):
                    # It exists but is not selected → lets try to cleanup
                    self.log(
                        f"Cleaning up old optional feature: {name}")
                    includes = feature.get("include", [])
                    remotes = feature.get("remote", [])
                    if includes:
                        # local dependency
                        for include in includes:
                            target = include.get("target")
                            dest_path = os.path.join(base_dir, target)
                            try:
                                os.remove(dest_path)
                                self.log(f"Removed local dependency: {target}")
                            except FileNotFoundError:
                                self.log(
                                    f"File for the local dependency not found: {target}")
                        pass
                    elif remotes:
                        # remote dependency
                        for remote in remotes:
                            target = remote.get("target")
                            dest_path = os.path.join(base_dir, target)
                            try:
                                os.remove(dest_path)
                                self.log(
                                    f"Removed remote dependency: {target}")
                            except FileNotFoundError:
                                self.log(
                                    f"File for the remote dependency not found: {target}")
                        pass
                    else:
                        # no cleanup to do, no includes and no remotes
                        self.log(
                            f"No remote and include present, we haven't done anything.")
                        continue
            else:
                # It doesn't exist in the list → maybe default behavior
                self.log(
                    f"The optional dependency {name} doesn't exist, we'll skip it.")
                continue

            self.log(f"<b>Applying optional feature:</b> {feature['name']}")

            # --- Handle include (local workspace files packed remotely) ---
            for include in feature.get("include", []):
                source = include.get("source")
                target = include.get("target", source)

                url = f"{self.package_base}/{pack_index['id']}/{source}"
                dest_path = os.path.join(base_dir, target)

                self.log(f"Downloading include: {source} → {target}")
                self.download_file(url, dest_path)

            # --- Handle remote (CDN-hosted files) ---
            for remote in feature.get("remote", []):
                url = remote.get("url")
                target = remote.get("target")
                if not url or not target:
                    continue

                dest_path = os.path.join(base_dir, target)
                self.log(f"Downloading remote: {url} → {target}")
                self.download_file(url, dest_path)

        self.log("<b>All files ready.</b>")
        self.finished.emit(pack_index, base_dir)
