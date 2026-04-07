from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout, QProgressBar
from PyQt6.QtCore import QProcess, pyqtSignal
import os


class LogWindow(QDialog):
    canceled = pyqtSignal()

    def __init__(self, parent=None, log_file_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Minecraft Log"))
        self.resize(800, 500)

        self._log_file_path = log_file_path
        if self._log_file_path:
            try:
                os.makedirs(os.path.dirname(self._log_file_path), exist_ok=True)
                with open(self._log_file_path, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                self._log_file_path = None

        self.process = QProcess(self)
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels)

        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.log_area = QPlainTextEdit()
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

    def _write_to_file(self, text: str) -> None:
        if not self._log_file_path or not text:
            return
        try:
            with open(self._log_file_path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    def close_window(self):
        self.canceled.emit()
        self.close()

    def closeEvent(self, event):
        self.canceled.emit()
        super().closeEvent(event)

    def force_close(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.log_area.appendPlainText(
                self.tr("[PROCESS TERMINATED BY USER]"))

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def set_max_progress(self, value: int):
        self.progress_bar.setRange(0, value)

    def start_process(self, java_args):
        self.set_progress(100)
        self.progress_bar.hide()
        msg = self.tr("Running Minecraft...\n")
        self.log_area.appendPlainText(msg)
        self._write_to_file(msg + "\n")
        self.process.start("java", java_args)

    def append_output(self):
        text = self.process.readAll().data().decode()
        self.log_area.appendPlainText(text)
        self._write_to_file(text)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def set_status(self, status):
        line = f"[STATUS] {status}"
        self.log_area.appendPlainText(line)
        self._write_to_file(line + "\n")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def on_finished(self):
        msg = self.tr("\nMinecraft closed.")
        self.log_area.appendPlainText(msg)
        self._write_to_file(msg + "\n")
