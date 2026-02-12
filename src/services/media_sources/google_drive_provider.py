"""Google Drive media source provider."""

import hashlib
import io
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from src.exceptions import (
    GoogleDriveAuthError,
    GoogleDriveError,
    GoogleDriveFileNotFoundError,
    GoogleDriveRateLimitError,
)
from src.services.media_sources.base_provider import MediaFileInfo, MediaSourceProvider
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
                raise GoogleDriveFileNotFoundError(
                    f"Google Drive file not found: {file_identifier}",
                    file_id=file_identifier,
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
                raise GoogleDriveFileNotFoundError(
                    f"Google Drive file not found: {file_identifier}",
                    file_id=file_identifier,
                )
            self._handle_http_error(
                e, context=f"calculate_file_hash({file_identifier})"
            )
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
