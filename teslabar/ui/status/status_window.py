"""Status window showing logs, errors, and vehicle state."""

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
)
from PySide6.QtCore import Qt, Slot

from teslabar.services.tesla_api import TeslaService, VehicleState


class LogHandler(logging.Handler):
    def __init__(self, text_edit: QTextEdit) -> None:
        super().__init__()
        self._text_edit = text_edit

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._text_edit.append(msg)


class StatusWindow(QWidget):
    def __init__(self, tesla_service: TeslaService, parent=None) -> None:
        super().__init__(parent)
        self._tesla = tesla_service

        self.setWindowTitle("TeslaBar - Status")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        # Vehicle state
        self._state_label = QLabel("State: unknown")
        self._state_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._state_label)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        self._cmd_label = QLabel("")
        self._cmd_label.setStyleSheet("color: #0066cc;")
        layout.addWidget(self._cmd_label)

        # Log area
        layout.addWidget(QLabel("Logs:"))
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self._log_text)

        # Install log handler
        self._log_handler = LogHandler(self._log_text)
        self._log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(self._log_handler)

        # Buttons
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self._log_text.clear)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def refresh(self) -> None:
        vd = self._tesla.vehicle_data
        state_text = vd.state.value.upper()
        self._state_label.setText(f"State: {state_text}")

        if vd.state == VehicleState.ERROR:
            self._state_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: red;"
            )
            self._error_label.setText(f"Error: {vd.error_message}")
        elif vd.state == VehicleState.ONLINE:
            self._state_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: green;"
            )
            self._error_label.setText("")
        else:
            self._state_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: orange;"
            )
            self._error_label.setText("")

        self._cmd_label.setText(self._tesla.command_status)

    def closeEvent(self, event) -> None:
        logging.getLogger().removeHandler(self._log_handler)
        super().closeEvent(event)
