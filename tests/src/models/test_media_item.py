"""Tests for MediaItem model definition."""

import pytest

from src.models.media_item import MediaItem


@pytest.mark.unit
class TestMediaItemModel:
    """Tests for MediaItem model column definitions and defaults."""

    def test_tablename(self):
        assert MediaItem.__tablename__ == "media_items"

    def test_id_default_generates_uuids(self):
        default_fn = MediaItem.id.default.arg
        assert callable(default_fn)
        assert default_fn.__name__ == "uuid4"

    def test_file_path_not_nullable(self):
        assert MediaItem.file_path.nullable is False

    def test_file_path_uniqueness_is_per_tenant(self):
        """file_path is unique per tenant via table-level UniqueConstraint, not column-level."""
        assert MediaItem.file_path.unique is not True
        constraint_names = [
            c.name for c in MediaItem.__table_args__ if hasattr(c, "name")
        ]
        assert "unique_file_path_per_tenant" in constraint_names

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
        item = MediaItem(file_name="test_image.jpg", times_posted=5)
        result = repr(item)
        assert "test_image.jpg" in result
        assert "5x" in result

    def test_chat_settings_id_nullable(self):
        assert MediaItem.chat_settings_id.nullable is True

    def test_repr_zero_posts(self):
        item = MediaItem(file_name="new_image.png", times_posted=0)
        result = repr(item)
        assert "new_image.png" in result
        assert "0x" in result
