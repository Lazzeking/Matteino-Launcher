from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton,
    QDialogButtonBox, QScrollArea, QWidget, QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from widgets.mod_entry_widget import ModEntryWidget


class DependencySelectionDialog(QDialog):
    def __init__(
        self,
        required: list,
        optional: list,
        unresolved_required: list = None,
        unresolved_optional: list = None,
        parent_mod: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Dependencies manager"))
        self.setMinimumSize(640, 600)
        unresolved_required = unresolved_required or []
        unresolved_optional = unresolved_optional or []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if parent_mod:
            title = parent_mod.get("title", self.tr("Unknown mod"))
            triggered_by = QLabel(
                self.tr("<b>Dependencies of:</b> {title}").format(title=title))
            triggered_by.setStyleSheet(
                "color: #ccc; font-size: 10pt; margin-bottom: 8px;")
            layout.addWidget(triggered_by)

        self.checkboxes = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        list_layout = QVBoxLayout(container)
        list_layout.setSpacing(10)
        list_layout.setContentsMargins(10, 10, 10, 10)

        # === Required Mods Section (will be added when you click OK) ===
        if required:
            list_layout.addWidget(
                QLabel(self.tr("<b>Mandatory dependencies</b> (will be added)")))
            for mod in required:
                entry = ModEntryWidget(mod, compact=True, readonly=True)
                entry.setMaximumWidth(560)
                list_layout.addWidget(entry)

        # === Optional Mods Section (select which to add) ===
        if optional:
            list_layout.addWidget(
                QLabel(self.tr("<b>Optional Dependencies</b> (check to add)")))
            for mod in optional:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)

                cb = QCheckBox()
                cb.setChecked(False)
                cb.mod_data = mod
                # Larger checkbox
                cb.setStyleSheet(
                    "QCheckBox { font-size: 14px; margin-top: 4px; }")
                self.checkboxes.append(cb)

                card = ModEntryWidget(mod, compact=True, readonly=True)
                card.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                card.setMaximumWidth(520)

                # Align checkbox to middle vertically
                row_layout.addWidget(cb, alignment=Qt.AlignmentFlag.AlignTop)
                row_layout.addWidget(card)
                list_layout.addWidget(row)

        # === Unresolved (no compatible version for current Minecraft/loader) ===
        unresolved_all = unresolved_required + unresolved_optional
        if unresolved_all:
            list_layout.addWidget(
                QLabel(self.tr(
                    "<b>Could not resolve</b> (no compatible version for your Minecraft/loader; add manually from Modrinth if needed):")))
            for mod in unresolved_all:
                title = mod.get("title", mod.get("project_id", "?"))
                url = mod.get("url", "")
                if url:
                    label = QLabel(f'<a href="{url}">{title}</a>')
                    label.setOpenExternalLinks(True)
                else:
                    label = QLabel(title)
                label.setStyleSheet("color: #888; font-size: 9pt; margin-left: 8px;")
                list_layout.addWidget(label)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # OK / Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_optional_mods(self):
        return [cb.mod_data for cb in self.checkboxes if cb.isChecked()]
