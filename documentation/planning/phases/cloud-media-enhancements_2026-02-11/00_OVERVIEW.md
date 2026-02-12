# Cloud Media Enhancements — Session Overview

**Session**: cloud-media-enhancements
**Date**: 2026-02-11
**Scope**: Remove filesystem dependency, enable cloud media sources (Google Drive), scheduled sync, and Instagram backfill
**Enhancements Planned**: 5

---

## User's Stated Goals

> "A user comes to use the product, they hook in their Google Drive folder, the system indexes their media, everything works from that external location."

> "They should sync and be indexed by the database on a schedule. New files, index. Deleted files, turn these off. Renames/moves -- ideally track."

> "A user could use the Instagram API to save their past media into the storage (backfill) and then add new posts in incrementals. This would be insanely helpful!"

**Key architectural constraint**: Users will NOT publicly host their media. Flow must be:
Cloud Storage → pull bytes → push to Cloudinary (temp) → Instagram API

---

## Phase Documents

| # | Title | Risk | Effort | Files | Tests | Dependencies |
|---|-------|------|--------|-------|-------|-------------|
| 01 | ~~Media Source Provider Abstraction~~ ✅ PR #41 | Low | Medium | 8 new, 7 modified | ~30 | None (foundation) |
| 02 | ~~Google Drive Provider~~ ✅ PR #42 | Medium | Large | 5 new, 5 modified | ~43 | Phase 01 |
| 03 | ~~Scheduled Media Sync Engine~~ ✅ PR #43 | Low | Medium | 3 new, 5 modified | ~38 | Phase 01, 02 |
| 04 | ~~Media Source Config & Health~~ ✅ PR #44 | Low | Medium | 2 new, 6 modified | ~15 | Phase 01, 02, 03 |
| 05 | ~~Instagram Media Backfill~~ ✅ PR #45 | Medium | Large | 6 new, 6 modified | ~55 | Phase 01, existing IG API |

---

## Dependency Graph

```
Phase 01: Provider Abstraction (foundation)
    │
    ├── Phase 02: Google Drive Provider
    │       │
    │       └── Phase 03: Scheduled Sync Engine
    │               │
    │               └── Phase 04: Config & Health UI
    │
    └── Phase 05: Instagram Backfill (also depends on existing IG API)
```

---

## Implementation Order

Phases **must** be implemented sequentially in order 01 → 02 → 03 → 04 due to hard dependencies.

Phase 05 depends on Phase 01 but NOT on Phases 02-04. It could theoretically be built in parallel with Phases 02-04 after Phase 01 is merged. However, sequential implementation is recommended to avoid merge conflicts in shared files (`media_repository.py`, `media_item.py`, `cli/main.py`, `telegram_commands.py`).

**Recommended order**: 01 → 02 → 03 → 04 → 05

---

## Parallel Safety Analysis

| Phase Pair | Parallel Safe? | Reason |
|-----------|---------------|--------|
| 01 + 02 | NO | 02 depends on 01's provider interface |
| 02 + 03 | NO | 03 depends on 02's Google Drive provider |
| 03 + 04 | NO | 04 depends on 03's MediaSyncService |
| 04 + 05 | POSSIBLE | Touch different files, but both modify `telegram_commands.py` and `media_repository.py` |

---

## Database Migrations

| Migration | Phase | Description |
|-----------|-------|-------------|
| 011 | Phase 01 | `source_type`, `source_identifier` columns on `media_items` |
| 012 | Phase 04 | `media_sync_enabled` column on `chat_settings` |
| 013 | Phase 05 | `instagram_media_id`, `backfilled_at` columns on `media_items` |

---

## New CLI Commands (across all phases)

| Command | Phase | Description |
|---------|-------|-------------|
| `connect-google-drive` | 02 | Connect Google Drive with service account credentials |
| `google-drive-status` | 02 | Show Google Drive connection status |
| `disconnect-google-drive` | 02 | Remove Google Drive credentials |
| `sync-media` | 03 | Manually trigger a media sync |
| `sync-status` | 03 | Show last sync run status |
| `backfill-instagram` | 05 | Backfill media from Instagram |
| `backfill-status` | 05 | Show backfill history |

---

## New Telegram Commands (across all phases)

| Command | Phase | Description |
|---------|-------|-------------|
| `/sync` | 04 | Trigger manual media sync from Telegram |
| `/backfill` | 05 | Trigger Instagram backfill from Telegram |

---

## New Settings (across all phases)

| Setting | Phase | Default | Description |
|---------|-------|---------|-------------|
| `MEDIA_SYNC_ENABLED` | 03 | `false` | Enable background sync loop |
| `MEDIA_SYNC_INTERVAL_SECONDS` | 03 | `300` | Sync interval (5 min) |
| `MEDIA_SOURCE_TYPE` | 03 | `"local"` | Provider type |
| `MEDIA_SOURCE_ROOT` | 03 | `""` | Provider root (path or folder ID) |
| `media_sync_enabled` (per-chat) | 04 | `false` | Per-chat sync toggle in Telegram |

---

## Estimated Total Effort

- **New files**: ~24
- **Modified files**: ~28 (some modified across multiple phases)
- **New tests**: ~168
- **Database migrations**: 3
- **New dependencies**: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`
