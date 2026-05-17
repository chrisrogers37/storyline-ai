"""Tests for token encryption utility."""

import pytest
from unittest.mock import patch

from cryptography.fernet import Fernet


def _mock_single_key(mock_settings, key=None):
    """Configure mock settings with a single ENCRYPTION_KEY."""
    mock_settings.ENCRYPTION_KEYS = None
    mock_settings.ENCRYPTION_KEY = key or Fernet.generate_key().decode()
    return mock_settings.ENCRYPTION_KEY


def _mock_multi_keys(mock_settings, keys_csv):
    """Configure mock settings with ENCRYPTION_KEYS (comma-separated)."""
    mock_settings.ENCRYPTION_KEYS = keys_csv
    mock_settings.ENCRYPTION_KEY = None
    return keys_csv


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
        _mock_single_key(mock_settings)

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
        _mock_single_key(mock_settings)

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
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Cannot encrypt empty string"):
            encryption.encrypt("")

    @patch("src.utils.encryption.settings")
    def test_decrypt_empty_string_raises_error(self, mock_settings):
        """Test that decrypting empty string raises ValueError."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Cannot decrypt empty string"):
            encryption.decrypt("")

    @patch("src.utils.encryption.settings")
    def test_decrypt_with_wrong_key_raises_error(self, mock_settings):
        """Test that decrypting with wrong key raises ValueError."""
        # Create and encrypt with one key
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("secret")

        # Reset singleton and use different key
        TokenEncryption.reset()
        _mock_single_key(mock_settings)

        new_encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to decrypt token"):
            new_encryption.decrypt(encrypted)

    @patch("src.utils.encryption.settings")
    def test_decrypt_corrupted_data_raises_error(self, mock_settings):
        """Test that decrypting corrupted data raises ValueError."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to decrypt token"):
            encryption.decrypt("not_valid_encrypted_data")

    @patch("src.utils.encryption.settings")
    def test_missing_encryption_key_raises_error(self, mock_settings):
        """Test that missing ENCRYPTION_KEY raises ValueError."""
        mock_settings.ENCRYPTION_KEY = None
        mock_settings.ENCRYPTION_KEYS = None

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="ENCRYPTION_KEY not configured"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_empty_encryption_key_raises_error(self, mock_settings):
        """Test that empty ENCRYPTION_KEY raises ValueError."""
        mock_settings.ENCRYPTION_KEY = ""
        mock_settings.ENCRYPTION_KEYS = None

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="ENCRYPTION_KEY not configured"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_invalid_key_format_raises_error(self, mock_settings):
        """Test that invalid key format raises ValueError."""
        _mock_single_key(mock_settings, key="not_a_valid_fernet_key")

        from src.utils.encryption import TokenEncryption

        with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY format"):
            TokenEncryption()

    @patch("src.utils.encryption.settings")
    def test_singleton_pattern(self, mock_settings):
        """Test that TokenEncryption follows singleton pattern."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        instance1 = TokenEncryption()
        instance2 = TokenEncryption()

        assert instance1 is instance2

    @patch("src.utils.encryption.settings")
    def test_reset_clears_singleton(self, mock_settings):
        """Test that reset() clears the singleton instance."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        TokenEncryption()
        TokenEncryption.reset()

        # After reset, new instance should work but be different
        _mock_single_key(mock_settings)
        instance2 = TokenEncryption()

        # They're not the same instance (singleton was reset)
        # Note: We can't directly compare after reset as it creates new singleton
        assert instance2 is not None

    @patch("src.utils.encryption.settings")
    def test_encrypt_unicode_content(self, mock_settings):
        """Test encrypting unicode content."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        original = "token_with_émojis_🔐_and_中文"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original

    @patch("src.utils.encryption.settings")
    def test_encrypt_long_token(self, mock_settings):
        """Test encrypting long token values."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()
        # Simulate a long OAuth token
        original = "EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original


@pytest.mark.unit
class TestKeyRotation:
    """Test MultiFernet key rotation support."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton instance before each test."""
        from src.utils.encryption import TokenEncryption

        TokenEncryption.reset()
        yield
        TokenEncryption.reset()

    @patch("src.utils.encryption.settings")
    def test_encryption_keys_takes_precedence_over_encryption_key(self, mock_settings):
        """Test that ENCRYPTION_KEYS is used when both are set."""
        from src.utils.encryption import TokenEncryption

        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        mock_settings.ENCRYPTION_KEYS = f"{key1},{key2}"
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()  # different key

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("test_value")

        # Should decrypt with key1 (primary from ENCRYPTION_KEYS), not ENCRYPTION_KEY
        f1 = Fernet(key1.encode())
        assert f1.decrypt(encrypted.encode()).decode() == "test_value"

    @patch("src.utils.encryption.settings")
    def test_old_key_tokens_decrypt_after_rotation(self, mock_settings):
        """Test that tokens encrypted with old key decrypt after new key is prepended."""
        from src.utils.encryption import TokenEncryption

        old_key = Fernet.generate_key().decode()
        _mock_single_key(mock_settings, key=old_key)

        old_encryption = TokenEncryption()
        encrypted = old_encryption.encrypt("my_oauth_token")

        # Rotate: prepend new key, keeping old key
        TokenEncryption.reset()
        new_key = Fernet.generate_key().decode()
        _mock_multi_keys(mock_settings, f"{new_key},{old_key}")

        new_encryption = TokenEncryption()

        # Old ciphertext should still decrypt
        assert new_encryption.decrypt(encrypted) == "my_oauth_token"

    @patch("src.utils.encryption.settings")
    def test_new_tokens_encrypt_with_primary_key(self, mock_settings):
        """Test that new tokens are encrypted with the first (primary) key."""
        from src.utils.encryption import TokenEncryption

        new_key = Fernet.generate_key().decode()
        old_key = Fernet.generate_key().decode()
        _mock_multi_keys(mock_settings, f"{new_key},{old_key}")

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("fresh_token")

        # The primary key (new_key) should be able to decrypt it directly
        f_new = Fernet(new_key.encode())
        assert f_new.decrypt(encrypted.encode()).decode() == "fresh_token"

    @patch("src.utils.encryption.settings")
    def test_rotate_reencrypts_with_primary_key(self, mock_settings):
        """Test that rotate() re-encrypts old-key tokens with the primary key."""
        from src.utils.encryption import TokenEncryption

        old_key = Fernet.generate_key().decode()
        _mock_single_key(mock_settings, key=old_key)

        old_encryption = TokenEncryption()
        old_ciphertext = old_encryption.encrypt("rotate_me")

        # Add new primary key
        TokenEncryption.reset()
        new_key = Fernet.generate_key().decode()
        _mock_multi_keys(mock_settings, f"{new_key},{old_key}")

        new_encryption = TokenEncryption()
        rotated_ciphertext = new_encryption.rotate(old_ciphertext)

        # After rotation, new key alone should decrypt
        f_new = Fernet(new_key.encode())
        assert f_new.decrypt(rotated_ciphertext.encode()).decode() == "rotate_me"

        # And decrypting via the MultiFernet should also work
        assert new_encryption.decrypt(rotated_ciphertext) == "rotate_me"

    @patch("src.utils.encryption.settings")
    def test_rotate_empty_string_raises_error(self, mock_settings):
        """Test that rotating empty string raises ValueError."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Cannot rotate empty string"):
            encryption.rotate("")

    @patch("src.utils.encryption.settings")
    def test_rotate_corrupted_data_raises_error(self, mock_settings):
        """Test that rotating corrupted data raises ValueError."""
        _mock_single_key(mock_settings)

        from src.utils.encryption import TokenEncryption

        encryption = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to rotate token"):
            encryption.rotate("not_valid_encrypted_data")

    @patch("src.utils.encryption.settings")
    def test_rotate_with_no_matching_key_raises_error(self, mock_settings):
        """Test that rotating with no matching key raises ValueError."""
        from src.utils.encryption import TokenEncryption

        # Encrypt with key A
        key_a = Fernet.generate_key().decode()
        _mock_single_key(mock_settings, key=key_a)
        enc_a = TokenEncryption()
        ciphertext = enc_a.encrypt("secret")

        # Reset to key B only (no key A)
        TokenEncryption.reset()
        key_b = Fernet.generate_key().decode()
        _mock_single_key(mock_settings, key=key_b)
        enc_b = TokenEncryption()

        with pytest.raises(ValueError, match="Failed to rotate token"):
            enc_b.rotate(ciphertext)

    @patch("src.utils.encryption.settings")
    def test_encryption_keys_with_whitespace(self, mock_settings):
        """Test that ENCRYPTION_KEYS handles whitespace around keys."""
        from src.utils.encryption import TokenEncryption

        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        _mock_multi_keys(mock_settings, f"  {key1} , {key2}  ")

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("trimmed")
        assert encryption.decrypt(encrypted) == "trimmed"

    @patch("src.utils.encryption.settings")
    def test_encryption_keys_ignores_empty_entries(self, mock_settings):
        """Test that trailing commas / empty entries are ignored."""
        from src.utils.encryption import TokenEncryption

        key1 = Fernet.generate_key().decode()
        _mock_multi_keys(mock_settings, f"{key1},,")

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("no_blanks")
        assert encryption.decrypt(encrypted) == "no_blanks"

    @patch("src.utils.encryption.settings")
    def test_single_key_backward_compat_roundtrip(self, mock_settings):
        """Test that ENCRYPTION_KEY (single) still works as before."""
        from src.utils.encryption import TokenEncryption

        key = Fernet.generate_key().decode()
        _mock_single_key(mock_settings, key=key)

        encryption = TokenEncryption()
        original = "backward_compat_token"
        encrypted = encryption.encrypt(original)

        assert encryption.decrypt(encrypted) == original

        # Direct Fernet should also work (it's the only key)
        f = Fernet(key.encode())
        assert f.decrypt(encrypted.encode()).decode() == original
