"""Password dialog with first-run vs. returning user flows."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from teslabar.crypto.credential_store import (
    credentials_exist,
    load_credentials,
    save_credentials,
)


class PasswordDialog(QDialog):
    MAX_ATTEMPTS = 3
    LOCKOUT_SECONDS = 60
    DELAY_SECONDS = 5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._attempts = 0
        self._password: str = ""
        self._credentials: dict = {}
        self._is_first_run = not credentials_exist()

        self.setWindowTitle("TeslaBar - Authentication")
        self.setFixedWidth(420)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        if self._is_first_run:
            self._build_first_run(layout)
        else:
            self._build_returning(layout)

    def _build_first_run(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel(
            "<b>Welcome to TeslaBar!</b><br>"
            "Set a password to encrypt your credentials.<br>"
            "You'll need this password each time you launch the app."
        ))

        pw_group = QGroupBox("Password")
        pw_layout = QFormLayout(pw_group)

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setPlaceholderText("Enter password")
        pw_layout.addRow("Password:", self._pw_input)

        self._pw_confirm = QLineEdit()
        self._pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_confirm.setPlaceholderText("Confirm password")
        pw_layout.addRow("Confirm:", self._pw_confirm)

        layout.addWidget(pw_group)

        cred_group = QGroupBox("Tesla OAuth Credentials")
        cred_layout = QFormLayout(cred_group)

        self._client_id_input = QLineEdit()
        self._client_id_input.setPlaceholderText("From developer.tesla.com")
        cred_layout.addRow("Client ID:", self._client_id_input)

        self._client_secret_input = QLineEdit()
        self._client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._client_secret_input.setPlaceholderText("From developer.tesla.com")
        cred_layout.addRow("Client Secret:", self._client_secret_input)

        layout.addWidget(cred_group)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: red;")
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        self._ok_btn = QPushButton("Save && Continue")
        self._ok_btn.clicked.connect(self._on_first_run_ok)
        self._ok_btn.setDefault(True)
        cancel_btn = QPushButton("Quit")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._ok_btn)
        layout.addLayout(btn_layout)

        self._pw_input.returnPressed.connect(self._on_first_run_ok)
        self._pw_confirm.returnPressed.connect(self._on_first_run_ok)
        self._client_secret_input.returnPressed.connect(self._on_first_run_ok)

    def _build_returning(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel(
            "<b>TeslaBar</b><br>"
            "Enter your password to unlock stored credentials."
        ))

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setPlaceholderText("Password")
        layout.addWidget(self._pw_input)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: red;")
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        self._ok_btn = QPushButton("Unlock")
        self._ok_btn.clicked.connect(self._on_returning_ok)
        self._ok_btn.setDefault(True)
        cancel_btn = QPushButton("Quit")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._ok_btn)
        layout.addLayout(btn_layout)

        self._pw_input.returnPressed.connect(self._on_returning_ok)

    def _on_first_run_ok(self) -> None:
        pw = self._pw_input.text()
        pw2 = self._pw_confirm.text()
        client_id = self._client_id_input.text().strip()
        client_secret = self._client_secret_input.text().strip()

        if not pw:
            self._status_label.setText("Password cannot be empty.")
            return
        if len(pw) < 4:
            self._status_label.setText("Password must be at least 4 characters.")
            return
        if pw != pw2:
            self._status_label.setText("Passwords do not match.")
            return
        if not client_id or not client_secret:
            self._status_label.setText("Client ID and Secret are required.")
            return

        self._password = pw
        self._credentials = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        save_credentials(self._credentials, pw)
        self.accept()

    def _on_returning_ok(self) -> None:
        pw = self._pw_input.text()
        if not pw:
            self._status_label.setText("Password cannot be empty.")
            return

        self._attempts += 1

        try:
            self._credentials = load_credentials(pw)
            self._password = pw
            self.accept()
        except Exception:
            remaining = self.MAX_ATTEMPTS - self._attempts
            if remaining <= 0:
                self._status_label.setText(
                    f"Too many attempts. Wait {self.LOCKOUT_SECONDS}s or quit."
                )
                self._ok_btn.setEnabled(False)
                self._pw_input.setEnabled(False)
                QTimer.singleShot(
                    self.LOCKOUT_SECONDS * 1000, self._reset_lockout
                )
            else:
                self._status_label.setText(
                    f"Wrong password. {remaining} attempt(s) left."
                )
                self._ok_btn.setEnabled(False)
                self._pw_input.setEnabled(False)
                QTimer.singleShot(
                    self.DELAY_SECONDS * 1000, self._re_enable
                )

    def _re_enable(self) -> None:
        self._ok_btn.setEnabled(True)
        self._pw_input.setEnabled(True)
        self._pw_input.setFocus()
        self._pw_input.selectAll()

    def _reset_lockout(self) -> None:
        self._attempts = 0
        self._re_enable()
        self._status_label.setText("You can try again now.")

    @property
    def password(self) -> str:
        return self._password

    @property
    def credentials(self) -> dict:
        return self._credentials
