import json
from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication


class BulkImportWorker(QObject):
    progress_changed = pyqtSignal(int)   # percentage
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_path, handler, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.handler = handler  # The object with handle_modrinth_url / handle_curseforge_url
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            already_added = {
                mod.get("project_id") for mod in self.handler.current_pack_data.get("files", [])
                if mod.get("project_id")
            }
            queue = []

            # Load input URLs
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                # JSON format
                data = json.loads(content)
                files = data.get("files", [])
                for file in files:
                    downloads = file.get("downloads", [])
                    if downloads:
                        queue.append(downloads[0])
            except json.JSONDecodeError:
                # Plain text list
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                queue.extend(line.split()[0] for line in lines)

            total_initial = len(queue) or 1
            processed_count = 0

            while queue and not self._stop:
                url = queue.pop(0)

                # Ensure handler sees bulk mode variables
                self.handler._bulk_dependency_queue = []
                self.handler._bulk_already_added = already_added

                # Pick the correct handler function
                if "modrinth.com" in url:
                    self.handler.handle_modrinth_url(
                        url, already_added=already_added)
                elif "curseforge.com" in url or "forgecdn.net" in url:
                    self.handler.handle_curseforge_url(
                        url, already_added=already_added)
                else:
                    print(f"Unknown URL skipped: {url}")

                # Update already_added from handler
                already_added = self.handler._bulk_already_added

                # Add dependencies (deduplicated)
                for dep_url in self.handler._bulk_dependency_queue:
                    if dep_url not in queue:
                        queue.append(dep_url)

                # Clear bulk mode vars to avoid leaks
                self.handler._bulk_dependency_queue.clear()
                del self.handler._bulk_dependency_queue
                del self.handler._bulk_already_added

                processed_count += 1
                self.progress_changed.emit(
                    int(processed_count / total_initial * 100))

                # Let Qt process events (UI stays responsive + GC runs)
                QCoreApplication.processEvents()

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))
