"""EC virtual key pair generation and management for Tesla Fleet API."""

import platform
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from teslabar.config import VIRTUAL_KEY_FILE, VIRTUAL_PUB_KEY_FILE


def generate_key_pair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    VIRTUAL_KEY_FILE.write_bytes(private_pem)
    VIRTUAL_PUB_KEY_FILE.write_bytes(public_pem)

    if platform.system() == "Darwin":
        _store_private_key_keychain(private_pem)

    return private_pem.decode(), public_pem.decode()


def _store_private_key_keychain(private_pem: bytes) -> None:
    try:
        import keyring
        keyring.set_password(
            "com.teslabar.virtualkey", "private_key", private_pem.decode()
        )
    except Exception:
        pass


def get_private_key_pem() -> str | None:
    if platform.system() == "Darwin":
        try:
            import keyring
            val = keyring.get_password("com.teslabar.virtualkey", "private_key")
            if val:
                return val
        except Exception:
            pass
    if VIRTUAL_KEY_FILE.exists():
        return VIRTUAL_KEY_FILE.read_text()
    return None


def get_public_key_pem() -> str | None:
    if VIRTUAL_PUB_KEY_FILE.exists():
        return VIRTUAL_PUB_KEY_FILE.read_text()
    return None


def key_pair_exists() -> bool:
    return VIRTUAL_PUB_KEY_FILE.exists() or get_private_key_pem() is not None


def get_github_pages_instructions(domain: str) -> str:
    pub_key = get_public_key_pem()
    if not pub_key:
        return "No public key found. Generate a key pair first."
    return (
        f"To register your virtual key with Tesla:\n\n"
        f"1. Create a GitHub repository with Pages enabled\n"
        f"2. Create the file:\n"
        f"   .well-known/appspecific/com.tesla.3p.public-key.pem\n"
        f"3. Paste this public key into that file:\n\n"
        f"{pub_key}\n"
        f"4. Your domain will be: {domain}\n"
        f"5. Open https://tesla.com/_ak/{domain} on your phone\n"
        f"6. Tap 'Allow' on your vehicle's screen"
    )
