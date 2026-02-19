from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QHBoxLayout,
    QTabWidget, QWidget, QVBoxLayout, QLabel
)


class OptionalFeatureDialog(QDialog):
    def __init__(self, feature=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Optional Feature")
        self.setMinimumHeight(300)
        self.setMinimumWidth(650)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        self.recommendation_input = QComboBox()
        self.recommendation_input.addItems(["normal", "recommended"])
        self.default_input = QCheckBox()
        self.include_input = QLineEdit()

        layout.addRow("Name:", self.name_input)
        layout.addRow("Description:", self.description_input)
        layout.addRow("Recommendation:", self.recommendation_input)
        layout.addRow("Selected by Default:", self.default_input)

        self.tabs = QTabWidget()

        # === Local Files Tab ===
        self.local_tab = QWidget()
        local_layout = QVBoxLayout()
        self.include_input = QLineEdit()
        local_layout.addWidget(QLabel("Local file globs (comma-separated):"))
        local_layout.addWidget(self.include_input)
        self.local_tab.setLayout(local_layout)

        # === Remote Files Tab ===
        self.remote_tab = QWidget()
        remote_layout = QFormLayout()
        self.remote_url_input = QLineEdit()
        self.remote_target_input = QLineEdit()
        remote_layout.addRow("Remote URL:", self.remote_url_input)
        remote_layout.addRow("Target Path (optional):",
                             self.remote_target_input)
        self.remote_tab.setLayout(remote_layout)

        # === Add tabs to widget ===
        self.tabs.addTab(self.local_tab, "Local Files")
        self.tabs.addTab(self.remote_tab, "Remote File")

        layout.addRow("Optional Feature Type:", self.tabs)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)

        layout.addRow(button_layout)

        if feature:
            self.name_input.setText(feature.get("name", ""))
            self.description_input.setText(feature.get("description", ""))
            self.recommendation_input.setCurrentText(
                feature.get("recommendation", "normal"))
            self.default_input.setChecked(
                feature.get("selectedByDefault", False))
            # Load include
            includes = feature.get("include", [])
            if includes:
                include_lines = []
                for item in includes:
                    if isinstance(item, dict):
                        src = item.get("source", "")
                        tgt = item.get("target", "")
                        if tgt:
                            include_lines.append(f"{src} => {tgt}")
                        else:
                            include_lines.append(src)
                    else:
                        include_lines.append(str(item))
                self.include_input.setText(", ".join(include_lines))
                self.tabs.setCurrentIndex(0)

            # Load remote
            remotes = feature.get("remote", [])
            if remotes:
                first = remotes[0]  # assuming one remote file
                self.remote_url_input.setText(first.get("url", ""))
                self.remote_target_input.setText(first.get("target", ""))
                self.tabs.setCurrentIndex(1)

    def get_feature(self):
        include_items = []
        remote_items = []

        if self.tabs.currentIndex() == 0:
            # Local files
            raw = self.include_input.text().strip()
            if raw:
                for part in raw.split(","):
                    part = part.strip()
                    if "=>" in part:
                        source, target = map(str.strip, part.split("=>", 1))
                        include_items.append(
                            {"source": source, "target": target})
                    else:
                        include_items.append({"source": part})
        else:
            # Remote file
            url = self.remote_url_input.text().strip()
            target = self.remote_target_input.text().strip()
            if url:
                remote_entry = {"url": url}
                if target:
                    remote_entry["target"] = target
                remote_items.append(remote_entry)

        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.text().strip(),
            "recommendation": self.recommendation_input.currentText(),
            "selectedByDefault": self.default_input.isChecked(),
            "include": include_items,
            "remote": remote_items
        }
