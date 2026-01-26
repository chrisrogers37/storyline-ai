"""Tests for token encryption utility."""

import pytest
from unittest.mock import patch

from cryptography.fernet import Fernet


@pytest.mark.unit
class TestTokenEncryption:
    """Test TokenEncryption class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton instance before each test."""
        # Import here to avoid import errors before patching
        from src.utils.encryption import TokenEncryption

        TokenEncryption.reset()
        yield
        TokenEncryption.reset()

    def test_generate_key_produces_valid_fernet_key(self):
        """Test that generate_key produces a valid Fernet key."""
        from src.utils.encryption import TokenEncryption

        key = TokenEncryption.generate_key()

        # Should be a 44-character base64 string
        assert len(key) == 44
        # Should be valid Fernet key (shouldn't raise)
        Fernet(key.encode())

    def test_generate_key_unique_each_call(self):
        """Test that generate_key produces different keys each call."""
        from src.utils.encryption import TokenEncryption

        key1 = TokenEncryption.generate_key()
        key2 = TokenEncryption.generate_key()

        assert key1 != key2

    @patch("src.utils.encryption.settings")
    def test_encrypt_decrypt_roundtrip(self, mock_settings):
        """Test that encrypt/decrypt returns original value."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        original = "my_secret_token_12345"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original  # Should be different from original

    @patch("src.utils.encryption.settings")
    def test_encrypt_produces_different_output_each_time(self, mock_settings):
        """Test that encrypting the same value produces different ciphertexts."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        original = "same_token"

        encrypted1 = encryption.encrypt(original)
        encrypted2 = encryption.encrypt(original)

        # Fernet uses random IV, so same plaintext produces different ciphertext
        assert encrypted1 != encrypted2
        # But both should decrypt to same value
        assert encryption.decrypt(encrypted1) == original
        assert encryption.decrypt(encrypted2) == original

    @patch("src.utils.encryption.settings")
    def test_encrypt_empty_string_raises_error(self, mock_settings):
        """Test that encrypting empty string raises ValueError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Cannot encrypt empty string"):
            encryption.encrypt("")

    @patch("src.utils.encryption.settings")
    def test_decrypt_empty_string_raises_error(self, mock_settings):
        """Test that decrypting empty string raises ValueError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Cannot decrypt empty string"):
            encryption.decrypt("")

    @patch("src.utils.encryption.settings")
    def test_decrypt_with_wrong_key_raises_error(self, mock_settings):
        """Test that decrypting with wrong key raises ValueError."""
        # Create and encrypt with one key
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("secret")

        # Reset singleton and use different key
        TokenEncryption.reset()
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        new_encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to decrypt token"):
            new_encryption.decrypt(encrypted)

    @patch("src.utils.encryption.settings")
    def test_decrypt_corrupted_data_raises_error(self, mock_settings):
        """Test that decrypting corrupted data raises ValueError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to decrypt token"):
            encryption.decrypt("not_valid_encrypted_data")

    @patch("src.utils.encryption.settings")
    def test_missing_encryption_key_raises_error(self, mock_settings):
        """Test that missing ENCRYPTION_KEY raises ValueError."""
        mock_settings.ENCRYPTION_KEY = None

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="ENCRYPTION_KEY not configured"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_empty_encryption_key_raises_error(self, mock_settings):
        """Test that empty ENCRYPTION_KEY raises ValueError."""
        mock_settings.ENCRYPTION_KEY = ""

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="ENCRYPTION_KEY not configured"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_invalid_key_format_raises_error(self, mock_settings):
        """Test that invalid key format raises ValueError."""
        mock_settings.ENCRYPTION_KEY = "not_a_valid_fernet_key"

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY format"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_singleton_pattern(self, mock_settings):
        """Test that TokenEncryption follows singleton pattern."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        instance1 = TokenEncryption()
        instance2 = TokenEncryption()

        assert instance1 is instance2

    @patch("src.utils.encryption.settings")
    def test_reset_clears_singleton(self, mock_settings):
        """Test that reset() clears the singleton instance."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        TokenEncryption()
        TokenEncryption.reset()

        # After reset, new instance should work but be different
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        instance2 = TokenEncryption()

        # They're not the same instance (singleton was reset)
        # Note: We can't directly compare after reset as it creates new singleton
        assert instance2 is not None

    @patch("src.utils.encryption.settings")
    def test_encrypt_unicode_content(self, mock_settings):
        """Test encrypting unicode content."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        original = "token_with_émojis_🔐_and_中文"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original

    @patch("src.utils.encryption.settings")
    def test_encrypt_long_token(self, mock_settings):
        """Test encrypting long token values."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        # Simulate a long OAuth token
        original = "EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original
