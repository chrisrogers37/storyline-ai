# Phase 02: Google Drive Provider

**PR Title**: feat: add Google Drive media source provider
**Risk Level**: Medium (new external integration, new dependencies, credential storage)
**Estimated Effort**: Large (5 new files, 4 modified files, ~42 new tests)
**Branch**: `enhance/cloud-media-enhancements/phase-02-google-drive-provider`

---

## Context

Phase 01 established the `MediaSourceProvider` interface and `LocalMediaProvider`. This phase delivers the primary cloud provider — Google Drive — enabling users to point the system at a Drive folder and have media sourced from there.

**User intent**: "Most people have Google Drive, it's low friction." Google Drive is the consumer onramp — lowest friction, everyone has an account, 15GB free.

**Flow**: Google Drive (private) -> download bytes -> system has the media -> Telegram (send bytes) or Cloudinary (temp public URL) -> Instagram API

---

## Dependencies

- **Depends on**: Phase 01 (Provider Abstraction — must be merged first)
- **Unlocks**: Phase 03 (Scheduled Sync), Phase 04 (Configuration)

---

## Detailed Implementation Plan

### Step 1: Add Google API Dependencies

#### Modify: `requirements.txt`

After the `cloudinary>=1.36.0` line, add:

```
# Google Drive (Cloud Media Phase 02)
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
```

---

### Step 2: Google Drive Exceptions

#### New File: `src/exceptions/google_drive.py`

```python
"""Google Drive related exceptions."""

from typing import Optional

from src.exceptions.base import StorylineError


class GoogleDriveError(StorylineError):
    """General Google Drive API error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_reason: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_reason = error_reason

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code:
            return f"{base} (status: {self.status_code})"
        return base


class GoogleDriveAuthError(GoogleDriveError):
    """Authentication or authorization error (invalid/expired credentials,
    or service account lacks folder access)."""

    def __init__(
        self,
        message: str = "Google Drive authentication failed",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class GoogleDriveRateLimitError(GoogleDriveError):
    """API rate limit exceeded (1000 queries per 100 seconds)."""

    def __init__(
        self,
        message: str = "Google Drive API rate limit exceeded",
        retry_after_seconds: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class GoogleDriveFileNotFoundError(GoogleDriveError):
    """File or folder not found or not accessible."""

    def __init__(
        self,
        message: str = "Google Drive file not found",
        file_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.file_id = file_id
```

#### Modify: `src/exceptions/__init__.py`

Add imports for all 4 new exceptions and add them to `__all__`:

```python
from src.exceptions.google_drive import (
    GoogleDriveError,
    GoogleDriveAuthError,
    GoogleDriveRateLimitError,
    GoogleDriveFileNotFoundError,
)
```

---

### Step 3: GoogleDriveProvider Implementation

#### New File: `src/services/media_sources/google_drive_provider.py`

Implements `MediaSourceProvider` for Google Drive API v3.

**Key design decisions:**
- Uses `google.oauth2.service_account.Credentials` for server-to-server auth
- Also accepts `google.oauth2.credentials.Credentials` for future OAuth user flow
- Root folder ID is the entry point — user shares a folder, gives us the ID
- Subfolders of root = categories (same convention as local filesystem)
- Uses Drive's `md5Checksum` for dedup (avoids downloading just to hash)
- `MediaIoBaseDownload` for chunked downloads (handles large videos)
- `_folder_cache` dict avoids redundant API calls for folder name resolution
- `_handle_http_error` converts Google `HttpError` into application exceptions

```python
"""Google Drive media source provider."""

import io
import hashlib
from datetime import datetime
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials

from src.services.media_sources.base_provider import MediaFileInfo, MediaSourceProvider
from src.exceptions import (
    GoogleDriveError,
    GoogleDriveAuthError,
    GoogleDriveRateLimitError,
    GoogleDriveFileNotFoundError,
)
from src.utils.logger import logger


class GoogleDriveProvider(MediaSourceProvider):
    """Media source provider for Google Drive.

    Accesses media files from a shared Google Drive folder via the
    Drive API v3. Subfolders of the root folder are treated as
    categories, matching the local filesystem convention.

    Supports two authentication modes:
        - Service Account: JSON key file for server-to-server access.
          The target folder must be shared with the service account email.
        - OAuth2 User Credentials: Access/refresh token for user's Drive.

    Args:
        root_folder_id: Google Drive folder ID to use as media root.
        service_account_info: Parsed JSON dict from service account key file.
        oauth_credentials: google.oauth2.credentials.Credentials instance.
    """

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    SUPPORTED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "video/mp4",
        "video/quicktime",
    }

    FILE_FIELDS = "id, name, mimeType, size, modifiedTime, md5Checksum, parents"
    LIST_FIELDS = f"nextPageToken, files({FILE_FIELDS})"
    PAGE_SIZE = 100

    def __init__(
        self,
        root_folder_id: str,
        service_account_info: Optional[dict] = None,
        oauth_credentials: Optional[UserCredentials] = None,
    ):
        self.root_folder_id = root_folder_id
        self._service = None

        if service_account_info:
            credentials = ServiceAccountCredentials.from_service_account_info(
                service_account_info, scopes=self.SCOPES
            )
        elif oauth_credentials:
            credentials = oauth_credentials
        else:
            raise GoogleDriveAuthError(
                "Google Drive provider requires either service_account_info "
                "or oauth_credentials."
            )

        self._credentials = credentials
        self._folder_cache: dict[str, str] = {}

    @property
    def service(self):
        """Lazy-initialize the Google Drive API service."""
        if self._service is None:
            self._service = build("drive", "v3", credentials=self._credentials)
        return self._service

    def list_files(self, folder: Optional[str] = None) -> list[MediaFileInfo]:
        """List media files in root folder or a specific subfolder."""
        try:
            if folder:
                folder_id = self._get_subfolder_id(folder)
                if not folder_id:
                    logger.warning(f"Google Drive subfolder not found: {folder}")
                    return []
                return self._list_files_in_folder(folder_id, folder_name=folder)
            else:
                all_files = []
                root_files = self._list_files_in_folder(
                    self.root_folder_id, folder_name=None
                )
                all_files.extend(root_files)

                subfolders = self._list_subfolders(self.root_folder_id)
                for subfolder_id, subfolder_name in subfolders:
                    subfolder_files = self._list_files_in_folder(
                        subfolder_id, folder_name=subfolder_name
                    )
                    all_files.extend(subfolder_files)

                return all_files
        except HttpError as e:
            self._handle_http_error(e, context="list_files")
            return []

    def download_file(self, file_identifier: str) -> bytes:
        """Download file content from Google Drive by file ID."""
        try:
            request = self.service.files().get_media(fileId=file_identifier)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(
                        f"Download progress for {file_identifier}: "
                        f"{int(status.progress() * 100)}%"
                    )

            buffer.seek(0)
            return buffer.read()
        except HttpError as e:
            if e.resp.status == 404:
                raise FileNotFoundError(
                    f"Google Drive file not found: {file_identifier}"
                )
            self._handle_http_error(e, context=f"download_file({file_identifier})")
            raise

    def get_file_info(self, file_identifier: str) -> Optional[MediaFileInfo]:
        """Get metadata for a Google Drive file without downloading."""
        try:
            file_meta = (
                self.service.files()
                .get(fileId=file_identifier, fields=self.FILE_FIELDS)
                .execute()
            )

            if file_meta.get("mimeType") not in self.SUPPORTED_MIME_TYPES:
                return None

            folder_name = self._resolve_folder_name(file_meta.get("parents", []))
            return self._build_file_info(file_meta, folder_name)
        except HttpError as e:
            if e.resp.status == 404:
                return None
            self._handle_http_error(e, context=f"get_file_info({file_identifier})")
            return None

    def file_exists(self, file_identifier: str) -> bool:
        """Check if a file exists and is accessible on Google Drive."""
        try:
            self.service.files().get(fileId=file_identifier, fields="id").execute()
            return True
        except HttpError:
            return False

    def get_folders(self) -> list[str]:
        """List subfolder names of the root folder (categories)."""
        try:
            subfolders = self._list_subfolders(self.root_folder_id)
            return sorted([name for _, name in subfolders])
        except HttpError as e:
            self._handle_http_error(e, context="get_folders")
            return []

    def is_configured(self) -> bool:
        """Check if credentials are valid and root folder is accessible."""
        try:
            self.service.files().get(
                fileId=self.root_folder_id, fields="id, name"
            ).execute()
            return True
        except Exception:
            return False

    def calculate_file_hash(self, file_identifier: str) -> str:
        """Get content hash using Drive's md5Checksum (avoids downloading).
        Falls back to SHA256 of downloaded content if md5Checksum unavailable."""
        try:
            file_meta = (
                self.service.files()
                .get(fileId=file_identifier, fields="id, md5Checksum")
                .execute()
            )

            md5 = file_meta.get("md5Checksum")
            if md5:
                return md5

            logger.info(
                f"No md5Checksum for {file_identifier}, downloading to compute hash"
            )
            file_bytes = self.download_file(file_identifier)
            return hashlib.sha256(file_bytes).hexdigest()
        except HttpError as e:
            if e.resp.status == 404:
                raise FileNotFoundError(
                    f"Google Drive file not found: {file_identifier}"
                )
            self._handle_http_error(e, context=f"calculate_file_hash({file_identifier})")
            raise

    # ==================== Private Helpers ====================

    def _list_files_in_folder(
        self, folder_id: str, folder_name: Optional[str] = None
    ) -> list[MediaFileInfo]:
        """List supported media files directly inside a folder."""
        mime_filter = " or ".join(
            f"mimeType='{mt}'" for mt in self.SUPPORTED_MIME_TYPES
        )
        query = f"'{folder_id}' in parents and trashed=false and ({mime_filter})"

        results = []
        page_token = None

        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    fields=self.LIST_FIELDS,
                    pageSize=self.PAGE_SIZE,
                    pageToken=page_token,
                )
                .execute()
            )

            for file_meta in response.get("files", []):
                info = self._build_file_info(file_meta, folder_name)
                if info:
                    results.append(info)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return results

    def _list_subfolders(self, parent_folder_id: str) -> list[tuple[str, str]]:
        """List immediate subfolders of a folder. Returns [(id, name), ...]."""
        query = (
            f"'{parent_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        subfolders = []
        page_token = None

        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name)",
                    pageSize=self.PAGE_SIZE,
                    pageToken=page_token,
                )
                .execute()
            )

            for folder_meta in response.get("files", []):
                folder_id = folder_meta["id"]
                folder_name = folder_meta["name"]
                self._folder_cache[folder_id] = folder_name
                subfolders.append((folder_id, folder_name))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return subfolders

    def _get_subfolder_id(self, folder_name: str) -> Optional[str]:
        """Find a subfolder by name under the root folder."""
        for fid, fname in self._folder_cache.items():
            if fname == folder_name:
                return fid

        query = (
            f"'{self.root_folder_id}' in parents "
            f"and name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        response = (
            self.service.files()
            .list(q=query, fields="files(id, name)", pageSize=1)
            .execute()
        )

        files = response.get("files", [])
        if files:
            folder_id = files[0]["id"]
            self._folder_cache[folder_id] = folder_name
            return folder_id

        return None

    def _resolve_folder_name(self, parent_ids: list[str]) -> Optional[str]:
        """Resolve category name from parent folder ID.
        Returns None if parent is root (no category)."""
        if not parent_ids:
            return None

        parent_id = parent_ids[0]

        if parent_id == self.root_folder_id:
            return None

        if parent_id in self._folder_cache:
            return self._folder_cache[parent_id]

        try:
            folder_meta = (
                self.service.files()
                .get(fileId=parent_id, fields="id, name, parents")
                .execute()
            )
            folder_name = folder_meta["name"]
            self._folder_cache[parent_id] = folder_name

            folder_parents = folder_meta.get("parents", [])
            if self.root_folder_id in folder_parents:
                return folder_name

            return None
        except HttpError:
            return None

    def _build_file_info(
        self, file_meta: dict, folder_name: Optional[str]
    ) -> Optional[MediaFileInfo]:
        """Build MediaFileInfo from Google Drive file metadata dict."""
        try:
            file_id = file_meta.get("id")
            name = file_meta.get("name", "")
            mime_type = file_meta.get("mimeType", "")
            size = int(file_meta.get("size", 0))

            if not file_id or not name:
                return None

            modified_at = None
            modified_str = file_meta.get("modifiedTime")
            if modified_str:
                modified_at = datetime.fromisoformat(
                    modified_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)

            return MediaFileInfo(
                identifier=file_id,
                name=name,
                size_bytes=size,
                mime_type=mime_type,
                folder=folder_name,
                modified_at=modified_at,
                hash=file_meta.get("md5Checksum"),
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Could not build file info for Drive file: {e}")
            return None

    def _handle_http_error(self, error: HttpError, context: str = "") -> None:
        """Convert Google HttpError to application exception."""
        status = error.resp.status
        reason = str(error)

        if status in (401, 403):
            logger.error(f"Google Drive auth error in {context}: {reason}")
            raise GoogleDriveAuthError(
                f"Authentication failed: {reason}", status_code=status
            )
        elif status == 404:
            logger.error(f"Google Drive not found in {context}: {reason}")
            raise GoogleDriveFileNotFoundError(
                f"Resource not found: {reason}", status_code=status
            )
        elif status == 429:
            logger.warning(f"Google Drive rate limit in {context}: {reason}")
            raise GoogleDriveRateLimitError(
                f"Rate limit exceeded: {reason}",
                status_code=status,
                retry_after_seconds=60,
            )
        else:
            logger.error(f"Google Drive API error ({status}) in {context}: {reason}")
            raise GoogleDriveError(f"API error: {reason}", status_code=status)
```

---

### Step 4: GoogleDriveService (Orchestration)

#### New File: `src/services/integrations/google_drive.py`

Wraps the provider with `BaseService` tracking. Handles credential storage/retrieval via encrypted `api_tokens` table (reuses existing Fernet encryption pattern from Instagram tokens).

```python
"""Google Drive integration service for media source management."""

import json
from typing import Optional

from src.services.base_service import BaseService
from src.services.media_sources.google_drive_provider import GoogleDriveProvider
from src.repositories.token_repository import TokenRepository
from src.utils.encryption import TokenEncryption
from src.exceptions import GoogleDriveAuthError, GoogleDriveError
from src.utils.logger import logger


class GoogleDriveService(BaseService):
    """Orchestration service for Google Drive media source.

    Handles credential retrieval from encrypted storage, provider creation,
    connection validation, and credential management.
    """

    SERVICE_NAME = "google_drive"
    TOKEN_TYPE_SERVICE_ACCOUNT = "service_account_json"

    def __init__(self):
        super().__init__()
        self.token_repo = TokenRepository()
        self._encryption: Optional[TokenEncryption] = None

    @property
    def encryption(self) -> TokenEncryption:
        """Lazy-load encryption to avoid errors when ENCRYPTION_KEY not set."""
        if self._encryption is None:
            self._encryption = TokenEncryption()
        return self._encryption

    def connect(
        self,
        credentials_json: str,
        root_folder_id: str,
    ) -> bool:
        """Set up Google Drive by storing credentials and validating access.

        Args:
            credentials_json: Service account JSON key file content (string)
            root_folder_id: Google Drive folder ID to use as media root

        Returns:
            True if connection successful

        Raises:
            GoogleDriveAuthError: If credentials are invalid
            GoogleDriveError: If folder is not accessible
            ValueError: If credentials_json is not valid JSON
        """
        with self.track_execution(
            method_name="connect",
            triggered_by="cli",
            input_params={"root_folder_id": root_folder_id},
        ) as run_id:
            try:
                creds_dict = json.loads(credentials_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid credentials JSON: {e}")

            cred_type = creds_dict.get("type", "")
            if cred_type != "service_account":
                raise ValueError(
                    f"Unsupported credential type: '{cred_type}'. "
                    f"Expected 'service_account'."
                )

            # Test connection before storing
            provider = GoogleDriveProvider(
                root_folder_id=root_folder_id,
                service_account_info=creds_dict,
            )

            if not provider.is_configured():
                raise GoogleDriveError(
                    f"Cannot access Google Drive folder: {root_folder_id}. "
                    f"Ensure the folder is shared with the service account email."
                )

            # Encrypt and store
            encrypted = self.encryption.encrypt(credentials_json)

            self.token_repo.create_or_update(
                service_name=self.SERVICE_NAME,
                token_type=self.TOKEN_TYPE_SERVICE_ACCOUNT,
                token_value=encrypted,
                metadata={
                    "root_folder_id": root_folder_id,
                    "credential_type": cred_type,
                    "service_account_email": creds_dict.get(
                        "client_email", "unknown"
                    ),
                },
            )

            logger.info(
                f"Google Drive connected. Root folder: {root_folder_id}, "
                f"Account: {creds_dict.get('client_email', 'N/A')}"
            )

            self.set_result_summary(run_id, {
                "success": True,
                "root_folder_id": root_folder_id,
                "credential_type": cred_type,
            })

            return True

    def validate_access(self, root_folder_id: Optional[str] = None) -> dict:
        """Validate that stored credentials can access the target folder.

        Returns:
            dict with: valid, folder_id, file_count, categories, error
        """
        with self.track_execution(
            method_name="validate_access",
            input_params={"root_folder_id": root_folder_id},
        ) as run_id:
            try:
                provider = self.get_provider(root_folder_id)

                if not provider.is_configured():
                    result = {"valid": False, "error": "Cannot access folder"}
                    self.set_result_summary(run_id, result)
                    return result

                folders = provider.get_folders()
                files = provider.list_files()

                result = {
                    "valid": True,
                    "folder_id": provider.root_folder_id,
                    "file_count": len(files),
                    "categories": folders,
                }

                self.set_result_summary(run_id, result)
                return result

            except (GoogleDriveAuthError, GoogleDriveError) as e:
                result = {"valid": False, "error": str(e)}
                self.set_result_summary(run_id, result)
                return result

    def get_provider(
        self, root_folder_id: Optional[str] = None
    ) -> GoogleDriveProvider:
        """Create a configured GoogleDriveProvider from stored credentials.

        Args:
            root_folder_id: Override the stored folder ID (optional).

        Raises:
            GoogleDriveAuthError: If no credentials stored or decryption fails.
        """
        db_token = self.token_repo.get_token(
            self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
        )

        if not db_token:
            raise GoogleDriveAuthError(
                "No Google Drive credentials found. "
                "Run 'storyline-cli connect-google-drive' first."
            )

        try:
            credentials_json = self.encryption.decrypt(db_token.token_value)
            creds_dict = json.loads(credentials_json)
        except (ValueError, json.JSONDecodeError) as e:
            raise GoogleDriveAuthError(
                f"Failed to decrypt Google Drive credentials: {e}"
            )

        if not root_folder_id:
            metadata = db_token.token_metadata or {}
            root_folder_id = metadata.get("root_folder_id")

        if not root_folder_id:
            raise GoogleDriveAuthError("No root_folder_id configured.")

        return GoogleDriveProvider(
            root_folder_id=root_folder_id,
            service_account_info=creds_dict,
        )

    def disconnect(self) -> bool:
        """Remove stored Google Drive credentials."""
        with self.track_execution(method_name="disconnect") as run_id:
            db_token = self.token_repo.get_token(
                self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
            )

            if not db_token:
                logger.info("No Google Drive credentials to remove")
                self.set_result_summary(run_id, {"success": False, "reason": "no_credentials"})
                return False

            self.token_repo.db.delete(db_token)
            self.token_repo.db.commit()

            logger.info("Google Drive credentials removed")
            self.set_result_summary(run_id, {"success": True})
            return True

    def get_connection_status(self) -> dict:
        """Check current Google Drive connection status."""
        db_token = self.token_repo.get_token(
            self.SERVICE_NAME, self.TOKEN_TYPE_SERVICE_ACCOUNT
        )

        if not db_token:
            return {"connected": False, "error": "No credentials configured"}

        metadata = db_token.token_metadata or {}

        return {
            "connected": True,
            "credential_type": metadata.get("credential_type", "unknown"),
            "service_account_email": metadata.get("service_account_email", "unknown"),
            "root_folder_id": metadata.get("root_folder_id", "unknown"),
        }
```

---

### Step 5: Factory Registration

#### Modify: `src/services/media_sources/factory.py`

Replace the Phase 01 version entirely. Key changes:
- Lazy import of `GoogleDriveProvider` (no crash if google SDK not installed)
- `create("google_drive")` loads credentials from DB via `GoogleDriveService` if no explicit auth kwargs provided
- `_ensure_google_drive_registered()` called before provider lookup

```python
"""Factory for creating media source provider instances."""

from src.services.media_sources.base_provider import MediaSourceProvider
from src.services.media_sources.local_provider import LocalMediaProvider
from src.config.settings import settings
from src.utils.logger import logger


class MediaSourceFactory:
    """Factory for creating MediaSourceProvider instances.

    Supports:
        - 'local': LocalMediaProvider (filesystem-based)
        - 'google_drive': GoogleDriveProvider (Google Drive API)
    """

    _providers: dict[str, type[MediaSourceProvider]] = {
        "local": LocalMediaProvider,
    }

    _google_drive_registered: bool = False

    @classmethod
    def _ensure_google_drive_registered(cls) -> None:
        """Lazily register GoogleDriveProvider to avoid import errors
        when google-api-python-client is not installed."""
        if cls._google_drive_registered:
            return
        try:
            from src.services.media_sources.google_drive_provider import (
                GoogleDriveProvider,
            )
            cls._providers["google_drive"] = GoogleDriveProvider
            cls._google_drive_registered = True
        except ImportError:
            logger.debug(
                "google-api-python-client not installed, "
                "Google Drive provider unavailable"
            )

    @classmethod
    def create(cls, source_type: str, **kwargs) -> MediaSourceProvider:
        """Create a provider instance for the given source type.

        Args:
            source_type: 'local' or 'google_drive'
            **kwargs: Provider-specific config.
                local: 'base_path' (defaults to settings.MEDIA_DIR)
                google_drive: 'root_folder_id', plus 'service_account_info'
                    or 'oauth_credentials'. If no auth provided, loads from DB.

        Raises:
            ValueError: If source_type is not supported.
        """
        cls._ensure_google_drive_registered()

        if source_type not in cls._providers:
            supported = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unsupported media source type: '{source_type}'. "
                f"Supported types: {supported}"
            )

        provider_class = cls._providers[source_type]

        if source_type == "local":
            base_path = kwargs.get("base_path", settings.MEDIA_DIR)
            return provider_class(base_path=base_path)

        if source_type == "google_drive":
            root_folder_id = kwargs.get("root_folder_id")
            service_account_info = kwargs.get("service_account_info")
            oauth_credentials = kwargs.get("oauth_credentials")

            if not service_account_info and not oauth_credentials:
                from src.services.integrations.google_drive import GoogleDriveService
                gdrive_service = GoogleDriveService()
                return gdrive_service.get_provider(root_folder_id)

            return provider_class(
                root_folder_id=root_folder_id,
                service_account_info=service_account_info,
                oauth_credentials=oauth_credentials,
            )

        return provider_class(**kwargs)

    @classmethod
    def get_provider_for_media_item(cls, media_item) -> MediaSourceProvider:
        """Get the appropriate provider for an existing media item.
        Falls back to 'local' if source_type is not set."""
        source_type = getattr(media_item, "source_type", None) or "local"
        return cls.create(source_type)

    @classmethod
    def register_provider(
        cls, source_type: str, provider_class: type[MediaSourceProvider]
    ) -> None:
        """Register a new provider type."""
        cls._providers[source_type] = provider_class
        logger.info(f"Registered media source provider: {source_type}")
```

---

### Step 6: CLI Commands

#### New File: `cli/commands/google_drive.py`

Three commands: `connect-google-drive`, `google-drive-status`, `disconnect-google-drive`

```python
"""Google Drive CLI commands for connecting and managing media sources."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.settings import settings

console = Console()


@click.command(name="connect-google-drive")
@click.option(
    "--credentials-file",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="Path to Google service account JSON key file",
)
@click.option(
    "--folder-id",
    required=True,
    help="Google Drive folder ID to use as media root",
)
def connect_google_drive(credentials_file, folder_id):
    """Connect Google Drive as a media source."""
    from src.services.integrations.google_drive import GoogleDriveService
    from src.exceptions import GoogleDriveAuthError, GoogleDriveError

    console.print(Panel.fit(
        "[bold blue]Connecting Google Drive[/bold blue]\n\n"
        f"Credentials: {credentials_file}\n"
        f"Folder ID: {folder_id}",
        title="Storyline AI",
    ))

    if not settings.ENCRYPTION_KEY:
        console.print("\n[bold red]Error:[/bold red] ENCRYPTION_KEY not configured in .env")
        return

    try:
        with open(credentials_file, "r") as f:
            credentials_json = f.read()
    except IOError as e:
        console.print(f"\n[red]Error reading credentials file:[/red] {e}")
        return

    console.print("\n[dim]Validating credentials and folder access...[/dim]")

    service = GoogleDriveService()

    try:
        service.connect(credentials_json=credentials_json, root_folder_id=folder_id)
    except (ValueError, GoogleDriveAuthError, GoogleDriveError) as e:
        console.print(f"\n[red]Error:[/red] {e}")
        return

    console.print("[dim]Checking folder contents...[/dim]")
    validation = service.validate_access(folder_id)

    console.print("\n[bold green]Google Drive connected![/bold green]\n")

    table = Table(title="Connection Details")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("Folder ID", folder_id)
    table.add_row("Media Files Found", str(validation.get("file_count", "N/A")))
    table.add_row("Categories", ", ".join(validation.get("categories", [])) or "None")
    table.add_row("Credentials", "Service Account (encrypted in DB)")
    console.print(table)


@click.command(name="google-drive-status")
def google_drive_status():
    """Check Google Drive connection status."""
    from src.services.integrations.google_drive import GoogleDriveService

    console.print("[bold blue]Google Drive Status[/bold blue]\n")

    service = GoogleDriveService()
    status = service.get_connection_status()

    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    if status["connected"]:
        table.add_row("Status", "[green]Connected[/green]")
        table.add_row("Credential Type", status.get("credential_type", "unknown"))
        table.add_row("Service Account", status.get("service_account_email", "unknown"))
        table.add_row("Root Folder ID", status.get("root_folder_id", "unknown"))
        console.print(table)

        console.print("\n[dim]Validating access...[/dim]")
        validation = service.validate_access()

        if validation["valid"]:
            console.print(f"[green]Folder accessible[/green]")
            console.print(f"  Files: {validation.get('file_count', 0)}")
            console.print(f"  Categories: {', '.join(validation.get('categories', [])) or 'None'}")
        else:
            console.print(f"[red]Folder not accessible:[/red] {validation.get('error')}")
    else:
        table.add_row("Status", "[red]Not Connected[/red]")
        table.add_row("Error", status.get("error", "Unknown"))
        console.print(table)
        console.print("\n[dim]Connect with: storyline-cli connect-google-drive --credentials-file <path> --folder-id <id>[/dim]")


@click.command(name="disconnect-google-drive")
def disconnect_google_drive():
    """Remove Google Drive credentials and disconnect."""
    from src.services.integrations.google_drive import GoogleDriveService

    service = GoogleDriveService()
    status = service.get_connection_status()

    if not status["connected"]:
        console.print("[yellow]No Google Drive connection to remove.[/yellow]")
        return

    if click.confirm(f"Disconnect Google Drive (account: {status.get('service_account_email', 'unknown')})?"):
        if service.disconnect():
            console.print("[green]Google Drive disconnected. Credentials removed.[/green]")
        else:
            console.print("[red]Failed to disconnect.[/red]")
    else:
        console.print("[dim]Cancelled[/dim]")
```

#### Modify: `cli/main.py`

Add import and registration of the 3 new commands:

```python
from cli.commands.google_drive import (
    connect_google_drive,
    google_drive_status,
    disconnect_google_drive,
)
```

And add to the CLI group:
```python
cli.add_command(connect_google_drive)
cli.add_command(google_drive_status)
cli.add_command(disconnect_google_drive)
```

---

## Test Plan

### New Test Files

#### `tests/src/services/media_sources/test_google_drive_provider.py` (~28 tests)

All tests use mocked Google API (no real API calls):
- **Init**: service account auth, OAuth auth, no auth raises error
- **is_configured**: success, failure
- **list_files**: root + subfolders, specific folder, nonexistent folder, API error
- **download_file**: success, not found (404)
- **get_file_info**: success, not found, unsupported MIME type
- **file_exists**: true, false
- **get_folders**: success, empty
- **calculate_file_hash**: md5Checksum available, fallback to SHA256, not found
- **_handle_http_error**: 401, 403, 404, 429 mapped to correct exceptions
- **_build_file_info**: complete metadata, missing id returns None, no modified time

#### `tests/src/services/test_google_drive_service.py` (~14 tests)

- **connect**: success, folder not accessible, invalid JSON, unsupported type
- **get_provider**: success, no credentials, override folder_id
- **disconnect**: success, no credentials
- **get_connection_status**: connected, not connected
- **validate_access**: success, failure

### Verification Commands

```bash
# Install new dependencies
pip install google-api-python-client google-auth google-auth-oauthlib

# Run new tests
pytest tests/src/services/media_sources/test_google_drive_provider.py -v
pytest tests/src/services/test_google_drive_service.py -v

# Full suite
pytest

# Lint
ruff check src/ tests/ cli/
ruff format --check src/ tests/ cli/
```

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Google SDK not installed | Factory skips registration; `create("google_drive")` raises `ValueError` with helpful message |
| Invalid service account JSON | `connect()` raises `ValueError` before storing anything |
| Folder not shared with service account | `connect()` validates access first, raises `GoogleDriveError` |
| Rate limit (429) | `GoogleDriveRateLimitError` raised with `retry_after_seconds=60` |
| File deleted from Drive between index and download | `download_file()` raises `FileNotFoundError` |
| Folder with 1000+ files | Pagination via `nextPageToken` handles this |
| Nested subfolders (2+ levels deep) | Only first-level subfolders are categories; deeper nesting ignored |
| Google Docs/Sheets in folder | Filtered out by `SUPPORTED_MIME_TYPES` (not image/video) |
| File renamed in Drive | File ID is stable — `source_identifier` doesn't change |

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Service Account over OAuth-only** | Simplest for server-to-server. User shares folder, no interactive consent flow needed. |
| **Lazy import in factory** | Google SDK is heavy. Local-only users shouldn't need it installed. |
| **Credentials in `api_tokens`** | Reuses existing encrypted storage. No new tables or migrations. |
| **`md5Checksum` for hash** | Drive API provides it for free. Avoids downloading files just to hash them. |
| **One level of subfolders** | Keeps category model simple. `memes/` and `merch/` work; `media/2024/memes/` doesn't. |

---

## Verification Checklist

- [ ] `pip install google-api-python-client google-auth google-auth-oauthlib` succeeds
- [ ] All imports resolve cleanly
- [ ] `MediaSourceFactory.create("google_drive")` raises `GoogleDriveAuthError` (no creds stored)
- [ ] `storyline-cli connect-google-drive --help` shows usage
- [ ] `storyline-cli google-drive-status` shows "Not Connected"
- [ ] All ~42 new tests pass
- [ ] Full test suite passes
- [ ] `ruff check` and `ruff format --check` pass
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT create a database migration.** Uses existing `api_tokens` table with `service_name='google_drive'`. No schema changes.
2. **Do NOT make `GoogleDriveProvider` extend `BaseService`.** Providers are lightweight per Phase 01 design.
3. **Do NOT implement OAuth user-consent flow in CLI.** Service Account is sufficient. OAuth constructor param exists for future use.
4. **Do NOT modify `MediaIngestionService` to index from Drive.** That's Phase 03 (Scheduled Sync).
5. **Do NOT add Drive settings to `chat_settings`.** That's Phase 04 (Configuration).
6. **Do NOT hardcode credentials or folder IDs.** Everything goes through encrypted `api_tokens`.
7. **Do NOT remove or modify `LocalMediaProvider`.** Factory changes are additive only.

---

## Files Summary

### New Files (5)
| File | Purpose |
|------|---------|
| `src/exceptions/google_drive.py` | Exception hierarchy (4 classes) |
| `src/services/media_sources/google_drive_provider.py` | MediaSourceProvider for Drive API v3 |
| `src/services/integrations/google_drive.py` | GoogleDriveService (BaseService orchestration) |
| `cli/commands/google_drive.py` | CLI: connect, status, disconnect |
| `tests/src/services/media_sources/test_google_drive_provider.py` | Provider tests (~28) |
| `tests/src/services/test_google_drive_service.py` | Service tests (~14) |

### Modified Files (4)
| File | Changes |
|------|---------|
| `requirements.txt` | Add 3 Google API dependencies |
| `src/exceptions/__init__.py` | Export 4 new exceptions |
| `src/services/media_sources/factory.py` | Register google_drive with lazy import + DB credential loading |
| `cli/main.py` | Import + register 3 new CLI commands |
