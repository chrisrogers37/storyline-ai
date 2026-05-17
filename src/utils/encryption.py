"""Token encryption utility for secure database storage.

Supports key rotation via MultiFernet. Set ENCRYPTION_KEYS (comma-separated,
newest first) to enable rotation. Falls back to single ENCRYPTION_KEY for
backward compatibility.
"""

import binascii
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet, InvalidToken

from src.config.settings import settings
from src.utils.logger import logger


class TokenEncryption:
    """
    Encrypt/decrypt sensitive tokens for database storage.

    Uses MultiFernet for key rotation support. Encrypts with the primary
    (first) key; decrypts by trying all keys in order.

    Key configuration (checked in order):
        1. ENCRYPTION_KEYS — comma-separated Fernet keys, newest first
        2. ENCRYPTION_KEY  — single key (backward compat, wrapped as MultiFernet)

    Rotation workflow:
        1. Generate new key: TokenEncryption.generate_key()
        2. Prepend to ENCRYPTION_KEYS: NEW_KEY,OLD_KEY
        3. Deploy — new tokens encrypt with NEW_KEY, old tokens still decrypt
        4. Run `storydump-cli rotate-keys` to re-encrypt all tokens with NEW_KEY
        5. Remove OLD_KEY from ENCRYPTION_KEYS

    Usage:
        encryption = TokenEncryption()
        encrypted = encryption.encrypt("my_secret_token")
        decrypted = encryption.decrypt(encrypted)
    """

    _instance: Optional["TokenEncryption"] = None
    _cipher: Optional[MultiFernet] = None

    def __new__(cls) -> "TokenEncryption":
        """Singleton pattern - reuse cipher instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize encryption cipher with key(s) from settings."""
        if self._cipher is not None:
            return

        keys_raw = getattr(settings, "ENCRYPTION_KEYS", None)
        single_key = settings.ENCRYPTION_KEY

        if keys_raw:
            key_strings = [k.strip() for k in keys_raw.split(",") if k.strip()]
        elif single_key:
            key_strings = [single_key]
        else:
            raise ValueError(
                "ENCRYPTION_KEY not configured. "
                'Generate one with: python -c "from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())"'
            )

        try:
            fernets = [Fernet(k.encode()) for k in key_strings]
            self._cipher = MultiFernet(fernets)
        except (ValueError, binascii.Error) as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a token with the primary (first) key.

        Args:
            plaintext: The sensitive token to encrypt

        Returns:
            Base64-encoded encrypted string (safe for database storage)
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a token, trying all configured keys in order.

        Args:
            ciphertext: The encrypted token from database

        Returns:
            Original plaintext token

        Raises:
            ValueError: If decryption fails (no matching key or corrupted data)
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")

        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.error("Token decryption failed - no matching key or corrupted data")
            raise ValueError(
                "Failed to decrypt token. "
                "This may indicate none of the configured keys can decrypt "
                "this data, or the data is corrupted."
            )

    def rotate(self, ciphertext: str) -> str:
        """
        Re-encrypt a token with the current primary key.

        Decrypts with whichever key works, then re-encrypts with the
        first key in ENCRYPTION_KEYS. Returns the original ciphertext
        unchanged if it was already encrypted with the primary key
        (MultiFernet.rotate handles this).

        Args:
            ciphertext: The encrypted token to re-encrypt

        Returns:
            Token re-encrypted with the primary key

        Raises:
            ValueError: If decryption fails (no matching key or corrupted data)
        """
        if not ciphertext:
            raise ValueError("Cannot rotate empty string")

        try:
            return self._cipher.rotate(ciphertext.encode()).decode()
        except InvalidToken:
            logger.error("Token rotation failed - no matching key or corrupted data")
            raise ValueError(
                "Failed to rotate token. "
                "This may indicate none of the configured keys can decrypt "
                "this data, or the data is corrupted."
            )

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key.

        Run this once during initial setup and store the result in .env:
            ENCRYPTION_KEY=<generated_key>

        For rotation, prepend the new key to ENCRYPTION_KEYS:
            ENCRYPTION_KEYS=<new_key>,<old_key>

        Returns:
            A new Fernet key (base64-encoded, 44 characters)
        """
        return Fernet.generate_key().decode()

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing or when encryption key changes.
        """
        cls._instance = None
        cls._cipher = None
