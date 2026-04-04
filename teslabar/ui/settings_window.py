"""Settings window for TeslaBar configuration."""

import io
import webbrowser

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

from teslabar.config import load_config, save_config
from teslabar.crypto.virtual_key import (
    key_pair_exists,
    generate_key_pair,
    get_public_key_pem,
    get_github_pages_instructions,
)


class SettingsWindow(QWidget):
    def __init__(self, tesla_service, password: str, parent=None) -> None:
        super().__init__(parent)
        self._tesla = tesla_service
        self._password = password

        self.setWindowTitle("TeslaBar - Settings")
        self.setMinimumWidth(520)
        self.setMinimumHeight(900)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        self._cfg = load_config()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # OAuth section
        oauth_group = QGroupBox("OAuth Credentials")
        oauth_layout = QFormLayout(oauth_group)

        self._client_id_input = QLineEdit(
            self._tesla._client_id if self._tesla else ""
        )
        oauth_layout.addRow("Client ID:", self._client_id_input)

        self._client_secret_input = QLineEdit(
            self._tesla._client_secret if self._tesla else ""
        )
        self._client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        oauth_layout.addRow("Client Secret:", self._client_secret_input)

        self._reauth_btn = QPushButton("Re-authenticate with Tesla")
        self._reauth_btn.clicked.connect(self._on_reauth)
        oauth_layout.addRow(self._reauth_btn)

        layout.addWidget(oauth_group)

        # General settings
        general_group = QGroupBox("General")
        general_layout = QFormLayout(general_group)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(5, 300)
        self._refresh_spin.setValue(self._cfg.get("refresh_interval_seconds", 15))
        self._refresh_spin.setSuffix(" seconds")
        general_layout.addRow("Refresh interval (window mode):", self._refresh_spin)

        self._temp_unit = QComboBox()
        self._temp_unit.addItems(["°C", "°F"])
        if self._cfg.get("temperature_unit", "C") == "F":
            self._temp_unit.setCurrentIndex(1)
        general_layout.addRow("Temperature unit:", self._temp_unit)

        self._region_combo = QComboBox()
        self._region_combo.addItems(["eu", "na", "cn"])
        current_region = self._cfg.get("region", "eu")
        idx = self._region_combo.findText(current_region)
        if idx >= 0:
            self._region_combo.setCurrentIndex(idx)
        general_layout.addRow("Tesla API region:", self._region_combo)

        layout.addWidget(general_group)

        # Virtual Key section
        vk_group = QGroupBox("Virtual Key")
        vk_layout = QVBoxLayout(vk_group)

        if not (self._tesla and self._tesla.partner_registered):
            setup_info = QLabel(
                "<b>Required for Tesla Fleet API access:</b><br><br>"
                "1. Generate a key pair below<br>"
                "2. Create a GitHub repo with Pages enabled<br>"
                "3. Host the public key at:<br>"
                "&nbsp;&nbsp;<code>https://&lt;domain&gt;/.well-known/appspecific/"
                "com.tesla.3p.public-key.pem</code><br>"
                "4. Enter your GitHub Pages domain below (e.g. username.github.io)<br>"
                "5. Save settings and restart the app<br>"
                "6. Open <code>https://tesla.com/_ak/&lt;domain&gt;</code> on your phone<br>"
                "7. Tap 'Allow' on your vehicle's screen to install the virtual key"
            )
            setup_info.setWordWrap(True)
            setup_info.setStyleSheet(
                "background-color: #ff0022; padding: 8px; border: 1px solid #ffc107; border-radius: 4px;"
            )

            setup_scroll = QScrollArea()
            setup_scroll.setWidget(setup_info)
            setup_scroll.setWidgetResizable(True)
            setup_scroll.setMinimumHeight(120)
            setup_scroll.setMaximumHeight(160)
            vk_layout.addWidget(setup_scroll)

        if key_pair_exists():
            vk_layout.addWidget(QLabel("Key pair exists."))
            pub_key = get_public_key_pem()
            if pub_key:
                pub_text = QTextEdit()
                pub_text.setPlainText(pub_key)
                pub_text.setReadOnly(True)
                pub_text.setMaximumHeight(100)
                vk_layout.addWidget(QLabel("Public key (copy this into your GitHub repo):"))
                vk_layout.addWidget(pub_text)
        else:
            no_key_label = QLabel("No virtual key pair found. Generate one first.")
            no_key_label.setStyleSheet("color: red; font-weight: bold;")
            vk_layout.addWidget(no_key_label)

        gen_btn = QPushButton(
            "Regenerate Key Pair" if key_pair_exists() else "Generate Key Pair"
        )
        gen_btn.clicked.connect(self._on_generate_key)
        vk_layout.addWidget(gen_btn)

        # GitHub Pages domain
        domain_layout = QFormLayout()
        self._domain_input = QLineEdit(
            self._cfg.get("github_pages_domain", "")
        )
        self._domain_input.setPlaceholderText("username.github.io")
        domain_layout.addRow("GitHub Pages domain:", self._domain_input)
        vk_layout.addLayout(domain_layout)

        self._show_instructions_btn = QPushButton("Show Setup Instructions")
        self._show_instructions_btn.clicked.connect(self._on_show_instructions)
        vk_layout.addWidget(self._show_instructions_btn)

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignCenter)
        vk_layout.addWidget(self._qr_label)

        self._show_qr_btn = QPushButton("Show QR Code for Key URL")
        self._show_qr_btn.clicked.connect(self._on_show_qr)
        vk_layout.addWidget(self._show_qr_btn)

        layout.addWidget(vk_group)

        # Save / Close
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        self._cfg["refresh_interval_seconds"] = self._refresh_spin.value()
        self._cfg["temperature_unit"] = (
            "F" if self._temp_unit.currentIndex() == 1 else "C"
        )
        self._cfg["region"] = self._region_combo.currentText()
        self._cfg["github_pages_domain"] = self._domain_input.text().strip()
        save_config(self._cfg)

        # Update OAuth creds if changed
        new_id = self._client_id_input.text().strip()
        new_secret = self._client_secret_input.text().strip()
        if new_id and new_secret and self._tesla:
            from teslabar.crypto.credential_store import (
                load_credentials,
                save_credentials,
            )
            try:
                creds = load_credentials(self._password)
            except Exception:
                creds = {}
            creds["client_id"] = new_id
            creds["client_secret"] = new_secret
            save_credentials(creds, self._password)
            self._tesla._client_id = new_id
            self._tesla._client_secret = new_secret

        QMessageBox.information(self, "Settings", "Settings saved.")
        self.close()

    def _on_reauth(self) -> None:
        if self._tesla and hasattr(self._tesla, "_reauth_callback"):
            self._tesla._reauth_callback()

    def _on_generate_key(self) -> None:
        _priv, pub = generate_key_pair()
        QMessageBox.information(
            self,
            "Key Generated",
            "Virtual key pair generated.\n\n"
            "Public key saved. See instructions for Tesla registration.",
        )
        self._build_ui()

    def _on_show_instructions(self) -> None:
        domain = self._domain_input.text().strip()
        if not domain:
            QMessageBox.warning(self, "Domain", "Enter your GitHub Pages domain first.")
            return
        instructions = get_github_pages_instructions(domain)
        QMessageBox.information(self, "Virtual Key Setup", instructions)

    def _on_show_qr(self) -> None:
        domain = self._domain_input.text().strip()
        if not domain:
            QMessageBox.warning(self, "Domain", "Enter your GitHub Pages domain first.")
            return
        url = f"https://tesla.com/_ak/{domain}"
        try:
            import qrcode

            qr = qrcode.make(url)
            buf = io.BytesIO()
            qr.save(buf, format="PNG")
            buf.seek(0)
            img = QImage()
            img.loadFromData(buf.read())
            pixmap = QPixmap.fromImage(img).scaled(
                200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._qr_label.setPixmap(pixmap)
        except ImportError:
            QMessageBox.warning(
                self, "QR", "Install qrcode library: pip install qrcode[pil]"
            )
