from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QProgressBar
from PyQt6.QtCore import QProcess, pyqtSignal, QPoint
from utils.base_dialog import BaseDialog


class LogWindow(BaseDialog):
    canceled = pyqtSignal()

    def __init__(self, parent=None, icon_path=None):
        super().__init__(parent, icon_path=icon_path)
        self.setWindowTitle(self.tr("Minecraft Log"))
        self.resize(800, 500)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels)

        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        btn_layout = QHBoxLayout()
        self.close_button = QPushButton(self.tr("Close"))
        self.kill_button = QPushButton(self.tr("Force Close"))

        self.close_button.clicked.connect(self.close_window)
        self.kill_button.clicked.connect(self.force_close)

        btn_layout.addStretch()
        btn_layout.addWidget(self.kill_button)
        btn_layout.addWidget(self.close_button)
        layout.addLayout(btn_layout)

        self.process.readyRead.connect(self.append_output)
        self.process.finished.connect(self.on_finished)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.parent():
            # Absolute screen coordinates
            self.move(100, 100)
        else:
            # Relative to parent (e.g., MainWindow)
            parent_pos = self.parent().pos()
            self.move(parent_pos - QPoint(400, 100))

    def close_window(self):
        self.canceled.emit()
        self.close()

    def closeEvent(self, event):
        self.canceled.emit()
        super().closeEvent(event)

    def force_close(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.log_area.append(
                self.tr("[PROCESS TERMINATED BY USER]"))

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def set_max_progress(self, value: int):
        self.progress_bar.setRange(0, value)

    def start_process(self, java_args):
        self.set_progress(100)
        self.progress_bar.hide()
        self.log_area.append(self.tr("Running Minecraft...\n"))
        self.process.start("java", java_args)

    def append_output(self):
        text = self.process.readAll().data().decode()
        self.log_area.append(text)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def set_status(self, status):
        self.log_area.append(
            f"[STATUS] {status}")  # Also log in output
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def log(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def on_finished(self):
        self.log_area.append(self.tr("\nMinecraft closed."))
        self.canceled.emit()
