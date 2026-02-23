# widgets/account_selector.py

import base64
import json
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt
from utils.base_dialog import BaseDialog


class AccountSelectorDialog(BaseDialog):
    def __init__(self, accounts, accounts_file_path, parent=None, icon_path=None):
        super().__init__(parent, icon_path=icon_path)
        self.setWindowTitle(self.tr("Select Account"))
        self.setFixedSize(320, 150)
        self.accounts = accounts
        self.accounts_file_path = accounts_file_path
        self.selected_uuid = None

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(
            self.handle_item_double_click)
        for uuid, data in self.accounts.get("accounts", {}).items():
            name = data.get("name", self.tr("Unknown") + "-" + uuid)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, uuid)

            avatar_pixmap = QPixmap()
            if "avatar_base64" in data:
                avatar_pixmap.loadFromData(
                    base64.b64decode(data["avatar_base64"]))
            else:
                try:
                    response = requests.get(
                        f"https://crafthead.net/avatar/{name}", timeout=5)
                    avatar_pixmap.loadFromData(response.content)
                except:
                    pass

            avatar_pixmap = avatar_pixmap.scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio)
            item.setIcon(QIcon(avatar_pixmap))
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        # Action buttons
        button_layout = QHBoxLayout()

        self.select_button = QPushButton(self.tr("Use Account"))
        self.select_button.clicked.connect(self.use_account)
        button_layout.addWidget(self.select_button)

        self.remove_button = QPushButton(self.tr("Remove Account"))
        self.remove_button.clicked.connect(self.remove_selected_account)
        button_layout.addWidget(self.remove_button)

        self.new_login_button = QPushButton(self.tr("Login New Account"))
        self.new_login_button.clicked.connect(self.login_new_account)

        layout.addLayout(button_layout)
        layout.addWidget(self.new_login_button)

    def handle_item_double_click(self, item):
        self.selected_uuid = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def use_account(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_uuid = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def populate_accounts(self):
        self.list_widget.clear()
        for uuid, data in self.accounts.get("accounts", {}).items():
            name = data.get("name", "(" + self.tr("Unknown") + ")")
            avatar = QPixmap()

            if "avatar_base64" in data:
                avatar.loadFromData(base64.b64decode(data["avatar_base64"]))

            item = QListWidgetItem(QIcon(avatar), name)
            item.setData(Qt.ItemDataRole.UserRole, uuid)
            self.list_widget.addItem(item)

        # Add "Login with new account"
        new_item = QListWidgetItem(self.tr("Login with new account"))
        new_item.setData(Qt.ItemDataRole.UserRole, "new")
        self.list_widget.addItem(new_item)

    def remove_selected_account(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        uuid = item.data(Qt.ItemDataRole.UserRole)
        if uuid == "new":
            return

        # Remove from internal data
        if uuid in self.accounts["accounts"]:
            del self.accounts["accounts"][uuid]

            # Handle selected account logic
            if self.accounts.get("selected") == uuid:
                self.accounts["selected"] = None

            # If no accounts remain, delete the selected key
            if not self.accounts["accounts"]:
                self.accounts.pop("selected", None)

            # Save updated file
            with open(self.accounts_file_path, "w") as f:
                json.dump(self.accounts, f, indent=4)

            # Refresh the list
            self.populate_accounts()

            # Always refresh main window so user image and login section stay in sync
            # (e.g. we removed the selected account or the last one)
            if self.parent():
                self.parent().refresh_ui()
            # If no accounts left, close the dialog
            if not self.accounts.get("accounts"):
                self.close()

    def login_new_account(self):
        self.selected_uuid = "new"
        self.accept()
