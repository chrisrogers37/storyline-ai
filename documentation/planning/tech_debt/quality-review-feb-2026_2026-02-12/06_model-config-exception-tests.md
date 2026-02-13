# Phase 06: Add Model, Config, and Exception Tests

**Status:** ✅ COMPLETE
**Started:** 2026-02-12
**Completed:** 2026-02-12
**PR Title:** `test: add unit tests for models, config, and exception hierarchy`
**Risk Level:** Low (test-only additions)
**Estimated Effort:** 3-4 hours
**Files Modified:**
- `tests/src/exceptions/test_base_exceptions.py` (new)
- `tests/src/exceptions/test_google_drive_exceptions.py` (new)
- `tests/src/exceptions/test_instagram_exceptions.py` (new)
- `tests/src/models/__init__.py` (new)
- `tests/src/models/test_media_item.py` (new)
- `tests/src/models/test_posting_queue.py` (new)
- `tests/src/models/test_chat_settings.py` (new)
- `tests/src/models/test_instagram_account.py` (new)
- `tests/src/models/test_api_token.py` (new)
- `tests/src/config/__init__.py` (new)
- `tests/src/config/test_constants.py` (new)
- `tests/src/config/test_settings.py` (new)

## Dependencies
- None (independent)

## Blocks
- None

## Context

Three areas of the codebase have 0% test coverage:

1. **12 model files** in `src/models/` — SQLAlchemy model definitions with column defaults, constraints, repr methods, and computed properties. The 5 most important models are prioritized.
2. **3 config files** in `src/config/` — Settings (Pydantic model with defaults + computed `database_url` property), constants, and database setup.
3. **3 exception files** — `base.py`, `google_drive.py`, `instagram.py` are untested. Only `backfill.py` has tests (in `test_backfill_exceptions.py`).

**Testing approach:** These tests inspect class metadata (column defaults, inheritance, properties) — they do NOT require a database connection. Model tests verify that SQLAlchemy column definitions have the expected defaults, nullability, and uniqueness. Exception tests verify inheritance hierarchy and attribute storage. Config tests verify default values and computed properties.

**Pattern to follow:** `tests/src/exceptions/test_backfill_exceptions.py` for exception test structure.

## Implementation Steps

### Part A: Exception Tests

#### Step 1: Read existing pattern

Read `tests/src/exceptions/test_backfill_exceptions.py` for the established test structure: class-per-exception, `@pytest.mark.unit`, test inheritance chain, test attributes, test string representation.

#### Step 2: Create `tests/src/exceptions/test_base_exceptions.py`

```python
"""Tests for base exception hierarchy."""

import pytest

from src.exceptions.base import StorylineError


@pytest.mark.unit
class TestStorylineError:
    """Tests for the StorylineError base exception."""

    def test_inherits_from_exception(self):
        """StorylineError inherits from Exception."""
        assert issubclass(StorylineError, Exception)

    def test_can_be_raised_and_caught(self):
        """StorylineError can be raised and caught."""
        with pytest.raises(StorylineError, match="test error"):
            raise StorylineError("test error")

    def test_caught_by_exception_handler(self):
        """StorylineError is caught by a generic Exception handler."""
        with pytest.raises(Exception):
            raise StorylineError("generic catch")

    def test_message_stored(self):
        """Error message is accessible via args."""
        err = StorylineError("my message")
        assert str(err) == "my message"
        assert err.args == ("my message",)

    def test_empty_message(self):
        """StorylineError works with empty message."""
        err = StorylineError()
        assert str(err) == ""
```

#### Step 3: Create `tests/src/exceptions/test_google_drive_exceptions.py`

```python
"""Tests for Google Drive exception classes."""

import pytest

from src.exceptions.base import StorylineError
from src.exceptions.google_drive import (
    GoogleDriveError,
    GoogleDriveAuthError,
    GoogleDriveFileNotFoundError,
    GoogleDriveQuotaError,
)


@pytest.mark.unit
class TestGoogleDriveError:
    """Tests for GoogleDriveError base class."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(GoogleDriveError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveError, match="drive error"):
            raise GoogleDriveError("drive error")

    def test_caught_by_storyline_error(self):
        with pytest.raises(StorylineError):
            raise GoogleDriveError("caught by parent")

    def test_message_and_details(self):
        err = GoogleDriveError("msg", details={"key": "val"})
        assert str(err) == "msg"
        assert err.details == {"key": "val"}

    def test_details_default_none(self):
        err = GoogleDriveError("msg")
        assert err.details is None


@pytest.mark.unit
class TestGoogleDriveAuthError:
    """Tests for GoogleDriveAuthError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveAuthError, GoogleDriveError)

    def test_inherits_from_storyline_error(self):
        assert issubclass(GoogleDriveAuthError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveAuthError, match="auth failed"):
            raise GoogleDriveAuthError("auth failed")

    def test_caught_by_parent(self):
        with pytest.raises(GoogleDriveError):
            raise GoogleDriveAuthError("caught")


@pytest.mark.unit
class TestGoogleDriveFileNotFoundError:
    """Tests for GoogleDriveFileNotFoundError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveFileNotFoundError, GoogleDriveError)

    def test_dual_inheritance_from_file_not_found(self):
        """Also inherits from built-in FileNotFoundError for compatibility."""
        assert issubclass(GoogleDriveFileNotFoundError, FileNotFoundError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveFileNotFoundError, match="not found"):
            raise GoogleDriveFileNotFoundError("not found")

    def test_caught_by_file_not_found(self):
        """Can be caught by FileNotFoundError handler."""
        with pytest.raises(FileNotFoundError):
            raise GoogleDriveFileNotFoundError("caught by builtin")

    def test_caught_by_google_drive_error(self):
        with pytest.raises(GoogleDriveError):
            raise GoogleDriveFileNotFoundError("caught by parent")

    def test_file_id_attribute(self):
        err = GoogleDriveFileNotFoundError("msg", file_id="abc123")
        assert err.file_id == "abc123"


@pytest.mark.unit
class TestGoogleDriveQuotaError:
    """Tests for GoogleDriveQuotaError."""

    def test_inherits_from_google_drive_error(self):
        assert issubclass(GoogleDriveQuotaError, GoogleDriveError)

    def test_can_be_raised(self):
        with pytest.raises(GoogleDriveQuotaError, match="quota exceeded"):
            raise GoogleDriveQuotaError("quota exceeded")

    def test_retry_after_attribute(self):
        err = GoogleDriveQuotaError("quota", retry_after_seconds=60)
        assert err.retry_after_seconds == 60

    def test_retry_after_default_none(self):
        err = GoogleDriveQuotaError("quota")
        assert err.retry_after_seconds is None
```

#### Step 4: Create `tests/src/exceptions/test_instagram_exceptions.py`

```python
"""Tests for Instagram and cloud exception classes."""

import pytest

from src.exceptions.base import StorylineError
from src.exceptions.instagram import (
    InstagramAPIError,
    RateLimitError,
    TokenExpiredError,
    CloudStorageError,
)


@pytest.mark.unit
class TestInstagramAPIError:
    """Tests for InstagramAPIError base class."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(InstagramAPIError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(InstagramAPIError, match="api error"):
            raise InstagramAPIError("api error")

    def test_caught_by_storyline_error(self):
        with pytest.raises(StorylineError):
            raise InstagramAPIError("caught by parent")

    def test_status_code_attribute(self):
        err = InstagramAPIError("msg", status_code=400)
        assert err.status_code == 400

    def test_status_code_default_none(self):
        err = InstagramAPIError("msg")
        assert err.status_code is None

    def test_response_body_attribute(self):
        err = InstagramAPIError("msg", response_body={"error": "bad"})
        assert err.response_body == {"error": "bad"}


@pytest.mark.unit
class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_inherits_from_instagram_api_error(self):
        assert issubclass(RateLimitError, InstagramAPIError)

    def test_inherits_from_storyline_error(self):
        assert issubclass(RateLimitError, StorylineError)

    def test_can_be_raised(self):
        with pytest.raises(RateLimitError, match="rate limited"):
            raise RateLimitError("rate limited")

    def test_caught_by_parent(self):
        with pytest.raises(InstagramAPIError):
            raise RateLimitError("caught")

    def test_retry_after_attribute(self):
        err = RateLimitError("limited", retry_after_seconds=120)
        assert err.retry_after_seconds == 120


@pytest.mark.unit
class TestTokenExpiredError:
    """Tests for TokenExpiredError."""

    def test_inherits_from_instagram_api_error(self):
        assert issubclass(TokenExpiredError, InstagramAPIError)

    def test_can_be_raised(self):
        with pytest.raises(TokenExpiredError, match="token expired"):
            raise TokenExpiredError("token expired")

    def test_caught_by_parent(self):
        with pytest.raises(InstagramAPIError):
            raise TokenExpiredError("caught")

    def test_token_type_attribute(self):
        err = TokenExpiredError("expired", token_type="access_token")
        assert err.token_type == "access_token"


@pytest.mark.unit
class TestCloudStorageError:
    """Tests for CloudStorageError."""

    def test_inherits_from_storyline_error(self):
        assert issubclass(CloudStorageError, StorylineError)

    def test_not_instagram_api_error(self):
        """CloudStorageError is separate from InstagramAPIError hierarchy."""
        assert not issubclass(CloudStorageError, InstagramAPIError)

    def test_can_be_raised(self):
        with pytest.raises(CloudStorageError, match="upload failed"):
            raise CloudStorageError("upload failed")

    def test_provider_attribute(self):
        err = CloudStorageError("failed", provider="cloudinary")
        assert err.provider == "cloudinary"

    def test_provider_default_none(self):
        err = CloudStorageError("failed")
        assert err.provider is None
```

### Part B: Model Tests

All model tests inspect SQLAlchemy class metadata (`.default.arg`, `.nullable`, `.unique`, `__tablename__`, `__repr__`). They do NOT require a database connection — this is pure Python.

#### Step 5: Create `tests/src/models/__init__.py`

Empty init file for the new test package.

```python
# (empty file)
```

#### Step 6: Create `tests/src/models/test_media_item.py`

```python
"""Tests for MediaItem model definition."""

import uuid

import pytest

from src.models.media_item import MediaItem


@pytest.mark.unit
class TestMediaItemModel:
    """Tests for MediaItem model column definitions and defaults."""

    def test_tablename(self):
        assert MediaItem.__tablename__ == "media_items"

    def test_id_default_is_uuid4(self):
        assert MediaItem.id.default.arg is uuid.uuid4

    def test_file_path_not_nullable(self):
        assert MediaItem.file_path.nullable is False

    def test_file_path_is_unique(self):
        assert MediaItem.file_path.unique is True

    def test_file_name_not_nullable(self):
        assert MediaItem.file_name.nullable is False

    def test_file_size_not_nullable(self):
        assert MediaItem.file_size.nullable is False

    def test_file_hash_not_nullable(self):
        assert MediaItem.file_hash.nullable is False

    def test_source_type_defaults_to_local(self):
        assert MediaItem.source_type.default.arg == "local"

    def test_source_type_not_nullable(self):
        assert MediaItem.source_type.nullable is False

    def test_requires_interaction_defaults_to_false(self):
        assert MediaItem.requires_interaction.default.arg is False

    def test_times_posted_defaults_to_zero(self):
        assert MediaItem.times_posted.default.arg == 0

    def test_is_active_defaults_to_true(self):
        assert MediaItem.is_active.default.arg is True

    def test_cloud_url_nullable(self):
        assert MediaItem.cloud_url.nullable is not False

    def test_instagram_media_id_is_unique(self):
        assert MediaItem.instagram_media_id.unique is True

    def test_repr_format(self):
        item = MediaItem.__new__(MediaItem)
        item.file_name = "test_image.jpg"
        item.times_posted = 5
        result = repr(item)
        assert "test_image.jpg" in result
        assert "5x" in result

    def test_repr_zero_posts(self):
        item = MediaItem.__new__(MediaItem)
        item.file_name = "new_image.png"
        item.times_posted = 0
        result = repr(item)
        assert "new_image.png" in result
        assert "0x" in result
```

#### Step 7: Create `tests/src/models/test_posting_queue.py`

```python
"""Tests for PostingQueue model definition."""

import uuid

import pytest

from src.models.posting_queue import PostingQueue


@pytest.mark.unit
class TestPostingQueueModel:
    """Tests for PostingQueue model column definitions and defaults."""

    def test_tablename(self):
        assert PostingQueue.__tablename__ == "posting_queue"

    def test_id_default_is_uuid4(self):
        assert PostingQueue.id.default.arg is uuid.uuid4

    def test_media_item_id_not_nullable(self):
        assert PostingQueue.media_item_id.nullable is False

    def test_scheduled_for_not_nullable(self):
        assert PostingQueue.scheduled_for.nullable is False

    def test_status_defaults_to_pending(self):
        assert PostingQueue.status.default.arg == "pending"

    def test_status_not_nullable(self):
        assert PostingQueue.status.nullable is False

    def test_retry_count_defaults_to_zero(self):
        assert PostingQueue.retry_count.default.arg == 0

    def test_max_retries_defaults_to_three(self):
        assert PostingQueue.max_retries.default.arg == 3

    def test_has_check_constraint(self):
        constraint_names = [
            c.name for c in PostingQueue.__table_args__ if hasattr(c, "name")
        ]
        assert "check_status" in constraint_names

    def test_repr_format(self):
        from datetime import datetime

        item = PostingQueue.__new__(PostingQueue)
        item.id = uuid.uuid4()
        item.status = "pending"
        item.scheduled_for = datetime(2026, 2, 12, 14, 0)
        result = repr(item)
        assert "pending" in result
        assert "2026" in result
```

#### Step 8: Create `tests/src/models/test_chat_settings.py`

```python
"""Tests for ChatSettings model definition."""

import uuid

import pytest

from src.models.chat_settings import ChatSettings


@pytest.mark.unit
class TestChatSettingsModel:
    """Tests for ChatSettings model column definitions and defaults."""

    def test_tablename(self):
        assert ChatSettings.__tablename__ == "chat_settings"

    def test_id_default_is_uuid4(self):
        assert ChatSettings.id.default.arg is uuid.uuid4

    def test_telegram_chat_id_not_nullable(self):
        assert ChatSettings.telegram_chat_id.nullable is False

    def test_telegram_chat_id_is_unique(self):
        assert ChatSettings.telegram_chat_id.unique is True

    def test_dry_run_mode_defaults_to_true(self):
        assert ChatSettings.dry_run_mode.default.arg is True

    def test_enable_instagram_api_defaults_to_false(self):
        assert ChatSettings.enable_instagram_api.default.arg is False

    def test_is_paused_defaults_to_false(self):
        assert ChatSettings.is_paused.default.arg is False

    def test_posts_per_day_defaults_to_three(self):
        assert ChatSettings.posts_per_day.default.arg == 3

    def test_posting_hours_start_defaults_to_14(self):
        assert ChatSettings.posting_hours_start.default.arg == 14

    def test_posting_hours_end_defaults_to_2(self):
        assert ChatSettings.posting_hours_end.default.arg == 2

    def test_show_verbose_notifications_defaults_to_true(self):
        assert ChatSettings.show_verbose_notifications.default.arg is True

    def test_media_sync_enabled_defaults_to_false(self):
        assert ChatSettings.media_sync_enabled.default.arg is False

    def test_active_instagram_account_id_nullable(self):
        assert ChatSettings.active_instagram_account_id.nullable is True

    def test_repr_format(self):
        item = ChatSettings.__new__(ChatSettings)
        item.telegram_chat_id = -1001234567
        item.is_paused = False
        result = repr(item)
        assert "-1001234567" in result
        assert "False" in result
```

#### Step 9: Create `tests/src/models/test_instagram_account.py`

```python
"""Tests for InstagramAccount model definition."""

import uuid

import pytest

from src.models.instagram_account import InstagramAccount


@pytest.mark.unit
class TestInstagramAccountModel:
    """Tests for InstagramAccount model column definitions and defaults."""

    def test_tablename(self):
        assert InstagramAccount.__tablename__ == "instagram_accounts"

    def test_id_default_is_uuid4(self):
        assert InstagramAccount.id.default.arg is uuid.uuid4

    def test_display_name_not_nullable(self):
        assert InstagramAccount.display_name.nullable is False

    def test_instagram_account_id_not_nullable(self):
        assert InstagramAccount.instagram_account_id.nullable is False

    def test_instagram_account_id_is_unique(self):
        assert InstagramAccount.instagram_account_id.unique is True

    def test_is_active_defaults_to_true(self):
        assert InstagramAccount.is_active.default.arg is True

    def test_repr_format(self):
        item = InstagramAccount.__new__(InstagramAccount)
        item.display_name = "My Brand"
        item.instagram_username = "mybrand"
        result = repr(item)
        assert "My Brand" in result
        assert "@mybrand" in result

    def test_repr_with_none_username(self):
        item = InstagramAccount.__new__(InstagramAccount)
        item.display_name = "My Brand"
        item.instagram_username = None
        result = repr(item)
        assert "My Brand" in result
        assert "@None" in result
```

#### Step 10: Create `tests/src/models/test_api_token.py`

The most complex model — has computed `is_expired` property and `hours_until_expiry()` method.

```python
"""Tests for ApiToken model definition and computed properties."""

import uuid
from datetime import datetime, timedelta

import pytest

from src.models.api_token import ApiToken


@pytest.mark.unit
class TestApiTokenModel:
    """Tests for ApiToken model column definitions and defaults."""

    def test_tablename(self):
        assert ApiToken.__tablename__ == "api_tokens"

    def test_id_default_is_uuid4(self):
        assert ApiToken.id.default.arg is uuid.uuid4

    def test_service_name_not_nullable(self):
        assert ApiToken.service_name.nullable is False

    def test_token_type_not_nullable(self):
        assert ApiToken.token_type.nullable is False

    def test_token_value_not_nullable(self):
        assert ApiToken.token_value.nullable is False

    def test_issued_at_not_nullable(self):
        assert ApiToken.issued_at.nullable is False

    def test_expires_at_nullable(self):
        assert ApiToken.expires_at.nullable is True

    def test_instagram_account_id_nullable(self):
        assert ApiToken.instagram_account_id.nullable is True

    def test_repr_with_expiry(self):
        token = ApiToken.__new__(ApiToken)
        token.service_name = "instagram"
        token.token_type = "access_token"
        token.expires_at = datetime(2026, 4, 1)
        result = repr(token)
        assert "instagram" in result
        assert "access_token" in result
        assert "expires" in result

    def test_repr_without_expiry(self):
        token = ApiToken.__new__(ApiToken)
        token.service_name = "shopify"
        token.token_type = "refresh_token"
        token.expires_at = None
        result = repr(token)
        assert "no expiry" in result


@pytest.mark.unit
class TestApiTokenIsExpired:
    """Tests for the is_expired computed property."""

    def test_not_expired_when_expires_at_is_none(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = None
        assert token.is_expired is False

    def test_not_expired_when_future(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = datetime.utcnow() + timedelta(days=30)
        assert token.is_expired is False

    def test_expired_when_past(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert token.is_expired is True


@pytest.mark.unit
class TestApiTokenHoursUntilExpiry:
    """Tests for the hours_until_expiry method."""

    def test_none_when_no_expiry(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = None
        assert token.hours_until_expiry() is None

    def test_positive_hours_when_future(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = datetime.utcnow() + timedelta(hours=48)
        hours = token.hours_until_expiry()
        assert hours is not None
        assert 47.9 < hours < 48.1

    def test_zero_when_past(self):
        token = ApiToken.__new__(ApiToken)
        token.expires_at = datetime.utcnow() - timedelta(hours=5)
        hours = token.hours_until_expiry()
        assert hours == 0
```

### Part C: Config Tests

#### Step 11: Create `tests/src/config/__init__.py`

Empty init file for the new test package.

```python
# (empty file)
```

#### Step 12: Create `tests/src/config/test_constants.py`

```python
"""Tests for shared application constants."""

import pytest

from src.config.constants import (
    MIN_POSTS_PER_DAY,
    MAX_POSTS_PER_DAY,
    MIN_POSTING_HOUR,
    MAX_POSTING_HOUR,
)


@pytest.mark.unit
class TestPostingConstants:
    """Tests for posting schedule constants."""

    def test_min_posts_per_day_is_positive(self):
        assert MIN_POSTS_PER_DAY >= 1

    def test_max_posts_per_day_greater_than_min(self):
        assert MAX_POSTS_PER_DAY > MIN_POSTS_PER_DAY

    def test_max_posts_per_day_is_reasonable(self):
        assert MAX_POSTS_PER_DAY <= 50

    def test_min_posting_hour_is_zero(self):
        assert MIN_POSTING_HOUR == 0

    def test_max_posting_hour_is_23(self):
        assert MAX_POSTING_HOUR == 23

    def test_posting_hour_range_covers_full_day(self):
        assert MAX_POSTING_HOUR - MIN_POSTING_HOUR == 23

    def test_specific_values_match_expected(self):
        assert MIN_POSTS_PER_DAY == 1
        assert MAX_POSTS_PER_DAY == 50
        assert MIN_POSTING_HOUR == 0
        assert MAX_POSTING_HOUR == 23
```

#### Step 13: Create `tests/src/config/test_settings.py`

Tests for the Settings Pydantic model. We test defaults and the `database_url` property — NOT actual `.env` loading.

```python
"""Tests for Settings configuration model."""

import pytest

from src.config.settings import Settings


@pytest.mark.unit
class TestSettingsDefaults:
    """Tests for Settings default values."""

    def _make_settings(self, **overrides):
        """Create a Settings instance with required fields and optional overrides."""
        defaults = {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "TELEGRAM_CHANNEL_ID": -1001234567,
            "ADMIN_TELEGRAM_CHAT_ID": 12345,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_enable_instagram_api_defaults_false(self):
        s = self._make_settings()
        assert s.ENABLE_INSTAGRAM_API is False

    def test_db_host_defaults_to_localhost(self):
        s = self._make_settings()
        assert s.DB_HOST == "localhost"

    def test_db_port_defaults_to_5432(self):
        s = self._make_settings()
        assert s.DB_PORT == 5432

    def test_db_name_defaults(self):
        s = self._make_settings()
        assert s.DB_NAME == "storyline_ai"

    def test_posts_per_day_defaults_to_3(self):
        s = self._make_settings()
        assert s.POSTS_PER_DAY == 3

    def test_posting_hours_start_defaults_to_14(self):
        s = self._make_settings()
        assert s.POSTING_HOURS_START == 14

    def test_posting_hours_end_defaults_to_2(self):
        s = self._make_settings()
        assert s.POSTING_HOURS_END == 2

    def test_repost_ttl_days_defaults_to_30(self):
        s = self._make_settings()
        assert s.REPOST_TTL_DAYS == 30

    def test_dry_run_mode_defaults_to_false(self):
        s = self._make_settings()
        assert s.DRY_RUN_MODE is False

    def test_log_level_defaults_to_info(self):
        s = self._make_settings()
        assert s.LOG_LEVEL == "INFO"

    def test_instagram_posts_per_hour_defaults_to_25(self):
        s = self._make_settings()
        assert s.INSTAGRAM_POSTS_PER_HOUR == 25

    def test_cloud_upload_retention_hours_defaults_to_24(self):
        s = self._make_settings()
        assert s.CLOUD_UPLOAD_RETENTION_HOURS == 24

    def test_media_sync_enabled_defaults_to_false(self):
        s = self._make_settings()
        assert s.MEDIA_SYNC_ENABLED is False

    def test_media_sync_interval_defaults_to_300(self):
        s = self._make_settings()
        assert s.MEDIA_SYNC_INTERVAL_SECONDS == 300

    def test_media_source_type_defaults_to_local(self):
        s = self._make_settings()
        assert s.MEDIA_SOURCE_TYPE == "local"

    def test_caption_style_defaults_to_enhanced(self):
        s = self._make_settings()
        assert s.CAPTION_STYLE == "enhanced"

    def test_cloud_storage_provider_defaults_to_cloudinary(self):
        s = self._make_settings()
        assert s.CLOUD_STORAGE_PROVIDER == "cloudinary"

    def test_optional_fields_default_to_none(self):
        s = self._make_settings()
        assert s.INSTAGRAM_ACCOUNT_ID is None
        assert s.INSTAGRAM_ACCESS_TOKEN is None
        assert s.FACEBOOK_APP_ID is None
        assert s.FACEBOOK_APP_SECRET is None
        assert s.CLOUDINARY_CLOUD_NAME is None
        assert s.CLOUDINARY_API_KEY is None
        assert s.CLOUDINARY_API_SECRET is None
        assert s.ENCRYPTION_KEY is None


@pytest.mark.unit
class TestSettingsDatabaseUrl:
    """Tests for the database_url computed property."""

    def _make_settings(self, **overrides):
        defaults = {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "TELEGRAM_CHANNEL_ID": -1001234567,
            "ADMIN_TELEGRAM_CHAT_ID": 12345,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_database_url_with_password(self):
        s = self._make_settings(DB_PASSWORD="secret123")
        url = s.database_url
        assert "secret123" in url
        assert url.startswith("postgresql://")
        assert "storyline_user" in url
        assert "storyline_ai" in url

    def test_database_url_without_password(self):
        s = self._make_settings(DB_PASSWORD="")
        url = s.database_url
        assert ":@" not in url
        assert "storyline_user@" in url

    def test_test_database_url_uses_test_db_name(self):
        s = self._make_settings(DB_PASSWORD="secret")
        url = s.test_database_url
        assert "storyline_ai_test" in url
        assert url != s.database_url

    def test_database_url_includes_host_and_port(self):
        s = self._make_settings(DB_HOST="myhost", DB_PORT=5433, DB_PASSWORD="pw")
        url = s.database_url
        assert "myhost" in url
        assert "5433" in url
```

## New Files Summary

| File | Tests | What It Covers |
|------|-------|----------------|
| `tests/src/exceptions/test_base_exceptions.py` | 5 | `StorylineError` inheritance, catchability |
| `tests/src/exceptions/test_google_drive_exceptions.py` | 21 | All 4 Google Drive exception classes |
| `tests/src/exceptions/test_instagram_exceptions.py` | 21 | All 4 Instagram/cloud exception classes |
| `tests/src/models/__init__.py` | -- | Package init |
| `tests/src/models/test_media_item.py` | 16 | Column defaults, nullability, repr |
| `tests/src/models/test_posting_queue.py` | 10 | Defaults, constraints, repr |
| `tests/src/models/test_chat_settings.py` | 14 | All setting defaults, repr |
| `tests/src/models/test_instagram_account.py` | 8 | Identity fields, uniqueness, repr |
| `tests/src/models/test_api_token.py` | 14 | Columns, repr, `is_expired`, `hours_until_expiry` |
| `tests/src/config/__init__.py` | -- | Package init |
| `tests/src/config/test_constants.py` | 7 | Constant values and ranges |
| `tests/src/config/test_settings.py` | 22 | Setting defaults, `database_url` property |

**Total new tests: ~138**

## Verification Checklist

- [x] `pytest tests/src/exceptions/ tests/src/models/ tests/src/config/ -v` — all 153 tests pass
- [x] `pytest` — full test suite passes (934 passed, 21 skipped)
- [x] `ruff check tests/src/exceptions/ tests/src/models/ tests/src/config/` — no lint errors
- [x] `ruff format --check tests/src/exceptions/ tests/src/models/ tests/src/config/` — no formatting issues
- [x] All tests are marked `@pytest.mark.unit`
- [x] No test requires a database connection
- [x] `pytest --cov=src/models --cov=src/config --cov=src/exceptions --cov-report=term-missing` — coverage improved
- [x] CHANGELOG.md updated

## What NOT To Do

- **Do NOT test SQLAlchemy internals** — Do not test that `Column()` creates columns. These are SQLAlchemy's responsibility.
- **Do NOT test database connectivity in model tests** — Model tests inspect class metadata only. No database needed.
- **Do NOT test the `database.py` module directly** — It initializes a live engine/session from the global `settings` instance at import time. Testing it requires a real database.
- **Do NOT test `ConfigValidator`** — That validator lives in `src/utils/validators.py`, not in `src/config/`. Testing it properly requires patching the global settings object.
- **Do NOT mock `datetime.utcnow` in model default tests** — We test that the default callable *is* `datetime.utcnow`, not that it produces a correct time. For `ApiToken.is_expired`, we use future/past offsets large enough that test execution time doesn't matter.
- **Do NOT create `tests/src/models/test_media_lock.py`** — While `MediaPostingLock` has interesting structure, its model definition is thin. The five priority models above cover the highest-value test surface.
- **Do NOT add `__init__.py` imports** — The test `__init__.py` files should remain empty. Test discovery uses pytest, not package imports.
