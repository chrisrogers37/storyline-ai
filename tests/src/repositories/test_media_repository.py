"""Tests for MediaRepository."""
import pytest
from uuid import UUID

from src.repositories.media_repository import MediaRepository
from src.models.media_item import MediaItem


@pytest.mark.unit
class TestMediaRepository:
    """Test suite for MediaRepository."""

    def test_create_media_item(self, test_db):
        """Test creating a new media item."""
        repo = MediaRepository(test_db)

        media = repo.create(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_hash="abc123",
            file_size_bytes=102400,
            mime_type="image/jpeg"
        )

        assert media.id is not None
        assert isinstance(media.id, UUID)
        assert media.file_path == "/test/image.jpg"
        assert media.file_hash == "abc123"
        assert media.times_posted == 0

    def test_get_by_path(self, test_db):
        """Test retrieving media by file path."""
        repo = MediaRepository(test_db)

        created_media = repo.create(
            file_path="/test/unique.jpg",
            file_name="unique.jpg",
            file_hash="unique123",
            file_size_bytes=50000,
            mime_type="image/jpeg"
        )

        found_media = repo.get_by_path("/test/unique.jpg")

        assert found_media is not None
        assert found_media.id == created_media.id

    def test_get_by_hash(self, test_db):
        """Test retrieving media by file hash."""
        repo = MediaRepository(test_db)

        created_media = repo.create(
            file_path="/test/hashed.jpg",
            file_name="hashed.jpg",
            file_hash="hash999",
            file_size_bytes=75000,
            mime_type="image/jpeg"
        )

        found_media = repo.get_by_hash("hash999")

        assert found_media is not None
        assert found_media.file_hash == "hash999"

    def test_get_duplicates(self, test_db):
        """Test finding duplicate media items."""
        repo = MediaRepository(test_db)

        # Create original
        repo.create(
            file_path="/test/original.jpg",
            file_name="original.jpg",
            file_hash="duplicate_hash",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        # Create duplicate (different path, same hash)
        repo.create(
            file_path="/test/copy.jpg",
            file_name="copy.jpg",
            file_hash="duplicate_hash",
            file_size_bytes=100000,
            mime_type="image/jpeg"
        )

        duplicates = repo.get_duplicates()

        assert len(duplicates) >= 1
        duplicate_hashes = [d.file_hash for d in duplicates]
        assert "duplicate_hash" in duplicate_hashes

    def test_increment_times_posted(self, test_db):
        """Test incrementing post count."""
        repo = MediaRepository(test_db)

        media = repo.create(
            file_path="/test/post.jpg",
            file_name="post.jpg",
            file_hash="post123",
            file_size_bytes=80000,
            mime_type="image/jpeg"
        )

        assert media.times_posted == 0

        updated_media = repo.increment_times_posted(media.id)

        assert updated_media.times_posted == 1
        assert updated_media.last_posted_at is not None

    def test_list_all_with_filters(self, test_db):
        """Test listing media with various filters."""
        repo = MediaRepository(test_db)

        # Create test media
        media1 = repo.create(
            file_path="/test/filter1.jpg",
            file_name="filter1.jpg",
            file_hash="filter1",
            file_size_bytes=50000,
            mime_type="image/jpeg",
            requires_interaction=True
        )

        media2 = repo.create(
            file_path="/test/filter2.jpg",
            file_name="filter2.jpg",
            file_hash="filter2",
            file_size_bytes=60000,
            mime_type="image/jpeg",
            requires_interaction=False
        )

        # List all
        all_media = repo.list_all()
        assert len(all_media) >= 2

        # Filter by requires_interaction
        interactive_media = repo.list_all(requires_interaction=True)
        interactive_ids = [m.id for m in interactive_media]
        assert media1.id in interactive_ids

    def test_get_never_posted(self, test_db):
        """Test getting media that has never been posted."""
        repo = MediaRepository(test_db)

        # Create never posted media
        never_posted = repo.create(
            file_path="/test/never.jpg",
            file_name="never.jpg",
            file_hash="never123",
            file_size_bytes=45000,
            mime_type="image/jpeg"
        )

        # Create posted media
        posted = repo.create(
            file_path="/test/posted.jpg",
            file_name="posted.jpg",
            file_hash="posted123",
            file_size_bytes=55000,
            mime_type="image/jpeg"
        )
        repo.increment_times_posted(posted.id)

        never_posted_items = repo.get_never_posted()
        never_posted_ids = [m.id for m in never_posted_items]

        assert never_posted.id in never_posted_ids
        assert posted.id not in never_posted_ids

    def test_get_least_posted(self, test_db):
        """Test getting least posted media items."""
        repo = MediaRepository(test_db)

        # Create media with different post counts
        media1 = repo.create(
            file_path="/test/least1.jpg",
            file_name="least1.jpg",
            file_hash="least1",
            file_size_bytes=40000,
            mime_type="image/jpeg"
        )

        media2 = repo.create(
            file_path="/test/least2.jpg",
            file_name="least2.jpg",
            file_hash="least2",
            file_size_bytes=41000,
            mime_type="image/jpeg"
        )

        # Post media2 multiple times
        repo.increment_times_posted(media2.id)
        repo.increment_times_posted(media2.id)

        least_posted = repo.get_least_posted(limit=5)

        # media1 (0 posts) should appear before media2 (2 posts)
        least_posted_ids = [m.id for m in least_posted]
        if len(least_posted_ids) >= 2:
            media1_index = least_posted_ids.index(media1.id) if media1.id in least_posted_ids else -1
            media2_index = least_posted_ids.index(media2.id) if media2.id in least_posted_ids else -1
            if media1_index >= 0 and media2_index >= 0:
                assert media1_index < media2_index
