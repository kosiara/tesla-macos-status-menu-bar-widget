"""AES-encrypted credential storage with macOS Keychain support."""

import base64
import json
import platform
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from teslabar.config import ENCRYPTED_CREDS_FILE, APP_DATA_DIR

SALT_FILE = APP_DATA_DIR / "salt.bin"
KEYCHAIN_SERVICE = "com.teslabar.credentials"


def _get_or_create_salt() -> bytes:
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = secrets.token_bytes(16)
    SALT_FILE.write_bytes(salt)
    return salt


def derive_key(password: str) -> bytes:
    salt = _get_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_data(data: dict, password: str) -> bytes:
    key = derive_key(password)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_data(encrypted: bytes, password: str) -> dict:
    key = derive_key(password)
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))


def save_credentials(creds: dict, password: str) -> None:
    encrypted = encrypt_data(creds, password)
    if platform.system() == "Darwin":
        try:
            import keyring
            encoded = base64.b64encode(encrypted).decode("ascii")
            keyring.set_password(KEYCHAIN_SERVICE, "encrypted_creds", encoded)
            return
        except Exception:
            pass
    ENCRYPTED_CREDS_FILE.write_bytes(encrypted)


def load_credentials(password: str) -> dict:
    encrypted = None
    if platform.system() == "Darwin":
        try:
            import keyring
            encoded = keyring.get_password(KEYCHAIN_SERVICE, "encrypted_creds")
            if encoded:
                encrypted = base64.b64decode(encoded)
        except Exception:
            pass
    if encrypted is None:
        if not ENCRYPTED_CREDS_FILE.exists():
            raise FileNotFoundError("No stored credentials found.")
        encrypted = ENCRYPTED_CREDS_FILE.read_bytes()
    return decrypt_data(encrypted, password)


def credentials_exist() -> bool:
    if platform.system() == "Darwin":
        try:
            import keyring
            val = keyring.get_password(KEYCHAIN_SERVICE, "encrypted_creds")
            if val:
                return True
        except Exception:
            pass
    return ENCRYPTED_CREDS_FILE.exists()


def clear_credentials() -> None:
    if platform.system() == "Darwin":
        try:
            import keyring
            keyring.delete_password(KEYCHAIN_SERVICE, "encrypted_creds")
        except Exception:
            pass
    if ENCRYPTED_CREDS_FILE.exists():
        ENCRYPTED_CREDS_FILE.unlink()
