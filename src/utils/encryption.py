"""Token encryption utility for secure database storage."""

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from src.config.settings import settings
from src.utils.logger import logger


class TokenEncryption:
    """
    Encrypt/decrypt sensitive tokens for database storage.

    Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
    The encryption key should be stored in .env as ENCRYPTION_KEY.

    Usage:
        # Encrypt before storing
        encryption = TokenEncryption()
        encrypted = encryption.encrypt("my_secret_token")

        # Decrypt when reading
        decrypted = encryption.decrypt(encrypted)

        # Generate a new key (one-time setup)
        key = TokenEncryption.generate_key()
    """

    _instance: Optional["TokenEncryption"] = None
    _cipher: Optional[Fernet] = None

    def __new__(cls) -> "TokenEncryption":
        """Singleton pattern - reuse cipher instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize encryption cipher with key from settings."""
        if self._cipher is not None:
            return

        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY not configured. "
                'Generate one with: python -c "from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())"'
            )

        try:
            self._cipher = Fernet(key.encode())
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a token.

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
        Decrypt a token.

        Args:
            ciphertext: The encrypted token from database

        Returns:
            Original plaintext token

        Raises:
            ValueError: If decryption fails (wrong key or corrupted data)
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")

        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.error("Token decryption failed - key mismatch or corrupted data")
            raise ValueError(
                "Failed to decrypt token. "
                "This may indicate the ENCRYPTION_KEY has changed or data is corrupted."
            )

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key.

        Run this once during initial setup and store the result in .env:
            ENCRYPTION_KEY=<generated_key>

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
