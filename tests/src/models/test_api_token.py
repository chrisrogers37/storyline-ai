"""Tests for ApiToken model definition and computed properties."""

from datetime import datetime, timedelta

import pytest

from src.models.api_token import ApiToken


@pytest.mark.unit
class TestApiTokenModel:
    """Tests for ApiToken model column definitions and defaults."""

    def test_tablename(self):
        assert ApiToken.__tablename__ == "api_tokens"

    def test_id_default_generates_uuids(self):
        default_fn = ApiToken.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

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
        token = ApiToken(
            service_name="instagram",
            token_type="access_token",
            expires_at=datetime(2026, 4, 1),
        )
        result = repr(token)
        assert "instagram" in result
        assert "access_token" in result
        assert "expires" in result

    def test_repr_without_expiry(self):
        token = ApiToken(
            service_name="shopify",
            token_type="refresh_token",
            expires_at=None,
        )
        result = repr(token)
        assert "no expiry" in result


@pytest.mark.unit
class TestApiTokenIsExpired:
    """Tests for the is_expired computed property."""

    def test_not_expired_when_expires_at_is_none(self):
        token = ApiToken(expires_at=None)
        assert token.is_expired is False

    def test_not_expired_when_future(self):
        token = ApiToken(expires_at=datetime.utcnow() + timedelta(days=30))
        assert token.is_expired is False

    def test_expired_when_past(self):
        token = ApiToken(expires_at=datetime.utcnow() - timedelta(hours=1))
        assert token.is_expired is True


@pytest.mark.unit
class TestApiTokenHoursUntilExpiry:
    """Tests for the hours_until_expiry method."""

    def test_none_when_no_expiry(self):
        token = ApiToken(expires_at=None)
        assert token.hours_until_expiry() is None

    def test_positive_hours_when_future(self):
        token = ApiToken(expires_at=datetime.utcnow() + timedelta(hours=48))
        hours = token.hours_until_expiry()
        assert hours is not None
        assert 47.9 < hours < 48.1

    def test_zero_when_past(self):
        token = ApiToken(expires_at=datetime.utcnow() - timedelta(hours=5))
        hours = token.hours_until_expiry()
        assert hours == 0
