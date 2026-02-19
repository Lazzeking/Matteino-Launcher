from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt

from utils.base_dialog import BaseDialog


class OptionalFeatureSelectorDialog(BaseDialog):
    def __init__(self, features, already_selected_features: list = [], parent=None, icon_path=None):
        super().__init__(parent, icon_path=icon_path)
        self.setWindowTitle("Select Optional Features")
        self.resize(600, 400)

        self.features = features
        self.checkboxes = []

        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(features), 4)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalHeaderLabels(
            ["Enable", "Name", "Description", "Recommendation"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, feat in enumerate(features):
            checkbox = QCheckBox()
            try:

                already_selected_feature = next(
                    (item for item in already_selected_features if item["name"] == feat["name"]), None)
                checkbox.setChecked(
                    already_selected_feature.get("selected", False))
                pass
            except Exception as e:
                checkbox.setChecked(feat.get("selectedByDefault", False))
                pass
            self.checkboxes.append(checkbox)

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, cell_widget)
            self.table.setItem(row, 1, QTableWidgetItem(feat.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(
                feat.get("description", "")))
            self.table.setItem(row, 3, QTableWidgetItem(
                feat.get("recommendation", "normal")))

        self.table.resizeRowsToContents()

        layout.addWidget(self.table)

        btns = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        layout.addLayout(btns)

    def get_selected_features(self):
        '''
        return [
            self.features[i]["name"]
            for i, cb in enumerate(self.checkboxes) if cb.isChecked()
        ]
        '''

        returnFeatures = []

        for i, feat in enumerate(self.features):
            returnFeatures.append({
                "name": feat["name"],
                "selectedByDefault": feat["selectedByDefault"],
                "selected": self.checkboxes[i].isChecked()
            })
        return returnFeatures
