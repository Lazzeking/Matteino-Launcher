import os

# Set by main window so we know where images live
_images_dir = None

# Path to down_chevron.png: from this file (launcherUser/utils/) -> launcherUser/resources/images/
_this_dir = os.path.dirname(os.path.abspath(__file__))
_default_chevron = os.path.normpath(os.path.join(_this_dir, "..", "resources", "images", "down_chevron.png"))


def set_images_dir(path):
    """Set the images directory (call from main window)."""
    global _images_dir
    _images_dir = path


def _chevron_stylesheet_url():
    """Return url(...) for down_chevron.png. Prefer path relative to cwd so Qt resolves it."""
    chevron = None
    if _images_dir:
        c = os.path.join(_images_dir, "down_chevron.png")
        if os.path.isfile(c):
            chevron = c
    if not chevron and os.path.isfile(_default_chevron):
        chevron = _default_chevron
    if not chevron:
        return "url(launcherUser/resources/images/down_chevron.png)"
    try:
        rel = os.path.relpath(chevron, os.getcwd()).replace("\\", "/")
        return "url(%s)" % rel
    except ValueError:
        abs_path = os.path.abspath(chevron).replace("\\", "/")
        prefix = "file://" if abs_path.startswith("/") else "file:///"
        return "url(%s%s)" % (prefix, abs_path)


def getBaseStylesheet(images_dir=None):
    images_dir = images_dir or _images_dir
    down_arrow_url = _chevron_stylesheet_url()
    return """
            QWidget {
                font-family: "Segoe UI", "Roboto", "Arial";
                font-size: 13px;
                background-color: #1e1e1e;
                color: #eeeeee;
            }

            QComboBox, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 8px;
                background-color: #2c2c2c;
                selection-background-color: #444;
            }

            QPushButton:hover {
                background-color: #3a3a3a;
            }

            QPushButton:pressed {
                background-color: #555;
            }

            QComboBox QAbstractItemView {
                background-color: #2c2c2c;
                selection-background-color: #444;
            }

            QTableWidget {
                gridline-color: #333;
                alternate-background-color: #252525;
            }

            QHeaderView::section {
                background-color: #2b2b2b;
                border: 1px solid #444;
                padding: 6px;
            }

            QCheckBox {
                spacing: 6px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #777;
                background: #2c2c2c;
            }

            QCheckBox::indicator:checked {
                background: #5e9c76;
            }

            QScrollBar:vertical, QScrollBar:horizontal {
                background: #222;
                width: 12px;
                height: 12px;
                margin: 0;
            }

            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #555;
                border-radius: 0;
            }
                           
            QComboBox {
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 28px 6px 8px;
                background-color: #2c2c2c;
                color: #eee;
            }

            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #444;
                background-color: #2c2c2c;
            }

            QComboBox::down-arrow {
                image: %s;
                width: 12px;
                height: 12px;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #444;
                background-color: #2c2c2c;
                selection-background-color: #444;
                color: #eee;
            }
                           
            QProgressBar {
                border: 1px solid #444;
                border-radius: 0px;
                background-color: #1e1e1e;
                height: 18px;
                text-align: center;
                color: #ccc;
                font-weight: bold;
            }

            QProgressBar::chunk {
                background-color: #5e9c76;
                margin: 0px;
                border-radius: 0px;
            }
        """ % down_arrow_url
