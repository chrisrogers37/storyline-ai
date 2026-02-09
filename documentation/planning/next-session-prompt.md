# Follow-Up Session Prompt

**Created**: 2026-02-09
**Purpose**: Prompt for a Claude session to execute three tasks: (1) Release v1.6.0, (2) Consolidate testing docs, (3) Race condition handling for Telegram button clicks.

Copy everything below the line into a new Claude session:

---

## Prompt

Please complete the following three tasks in order. All work should be committed and pushed when complete.

### Task 1: Release v1.6.0

The `[Unreleased]` section in `CHANGELOG.md` is massive (~350 lines) covering Phase 1.7 (inline account selector), Phase 1.8 (TelegramService refactor, verbose expansion, /cleanup command), plus numerous bug fixes and CI work. This should be cut as v1.6.0.

**Steps:**

1. **Read `CHANGELOG.md`** and understand the structure.

2. **Create a new `## [1.6.0] - 2026-02-09` section** below `## [Unreleased]`:
   - Move ALL current Unreleased content into this new section.
   - Organize it cleanly under the standard Keep a Changelog categories: `### Added`, `### Changed`, `### Fixed`.
   - Deduplicate the multiple `### Fixed` and `### Changed` subsections (the Unreleased section currently has several duplicated category headers that should be merged).
   - Group logically: TelegramService refactor entries together, Phase 1.7 together, Phase 1.8 together, bug fixes together.
   - Leave `## [Unreleased]` empty (just the header).

3. **Add comparison link** at the bottom of the file:
   ```
   [1.6.0]: https://github.com/chrisrogers37/storyline-ai/compare/v1.5.0...v1.6.0
   ```
   Update the `[Unreleased]` link to compare against v1.6.0:
   ```
   [Unreleased]: https://github.com/chrisrogers37/storyline-ai/compare/v1.6.0...HEAD
   ```

4. **Update `src/__init__.py`**: Change `__version__ = "1.4.0"` to `__version__ = "1.6.0"`.

5. **Update version references** across docs:
   - `documentation/ROADMAP.md`: Update "Next Version" from TBD to v1.6.0 with today's date. Add v1.6.0 row to version history table.
   - `documentation/README.md`: Update current version to v1.6.0.
   - `README.md` (root): Update version if mentioned.

6. **Do NOT create a git tag** — the user will do that manually after review. Just commit the changes.

### Task 2: Consolidate Testing Documentation

Two testing docs overlap significantly:
- `documentation/guides/testing.md` — "Automatic Test Database Setup" (268 lines, tutorial-style, explains the auto-DB pattern)
- `documentation/guides/testing-guide.md` — "Testing Guide" (359 lines, practical guide with test structure, fixtures, writing tests, CI)

**Steps:**

1. **Read both files** completely.

2. **Merge into a single `documentation/guides/testing-guide.md`**:
   - Keep the practical structure from `testing-guide.md` (Quick Start, Test Structure, Markers, Fixtures, Writing Tests, CI, Troubleshooting)
   - Incorporate the auto-DB setup explanation from `testing.md` as a section (but trim the excessive cheerfulness and marketing-style language — write it as a straightforward technical doc)
   - Remove the comparison tables ("Our approach vs SQLite in-memory") — just document what we use
   - Keep the `.env.test` configuration section (from either file)
   - Ensure the test structure tree matches what's actually in the codebase (the tree was updated in the previous session to include all 17 service test files, 8 repo files, 5 util files)
   - Update test count to 488
   - Remove the "147 comprehensive tests" reference from testing.md (it's from v1.0.1)

3. **Delete `documentation/guides/testing.md`** (the content is now in testing-guide.md).

4. **Update references**:
   - `documentation/README.md` currently lists both files. Remove the `testing.md` reference, keep only `testing-guide.md`.
   - `CLAUDE.md` references both — update to reference only `testing-guide.md`.
   - Check if any other docs link to `testing.md` and update them.

### Task 3: Race Condition Handling for Telegram Button Clicks

This is documented as a backlog item in `documentation/planning/phases/00_MASTER_ROADMAP.md` (line ~415). The problem: multiple rapid button clicks can trigger duplicate operations (e.g., clicking "Posted" twice creates two history entries and tries to delete the queue item twice).

**Context:**
- Callback handlers are in `src/services/core/telegram_callbacks.py` (class `TelegramCallbackHandlers`)
- Auto-post handler is in `src/services/core/telegram_autopost.py` (class `TelegramAutopostHandler`)
- Account handlers are in `src/services/core/telegram_accounts.py`
- The main callback router is in `src/services/core/telegram_service.py` (`_handle_callback` method)
- All handlers use the composition pattern — they receive a `TelegramService` reference via `self.service`

**The proposed solution from the roadmap:**
1. Track pending operations per `queue_id` with cancellation tokens
2. Use `asyncio.Lock` to prevent concurrent execution on the same item
3. Terminal actions (Skip/Posted/Reject) cancel any pending Auto Post
4. Same button clicked twice cancels current operation
5. Visual feedback: "⏳ Processing..." state distinct from idle

**Implementation steps:**

1. **Read all handler files** to understand the current flow.

2. **Add operation lock infrastructure to `TelegramService`** (`telegram_service.py`):
   ```python
   import asyncio

   # In __init__:
   self._operation_locks: dict[str, asyncio.Lock] = {}
   self._cancel_flags: dict[str, asyncio.Event] = {}

   def get_operation_lock(self, queue_id: str) -> asyncio.Lock:
       """Get or create an asyncio lock for a queue item."""
       if queue_id not in self._operation_locks:
           self._operation_locks[queue_id] = asyncio.Lock()
       return self._operation_locks[queue_id]

   def get_cancel_flag(self, queue_id: str) -> asyncio.Event:
       """Get or create a cancellation flag for a queue item."""
       if queue_id not in self._cancel_flags:
           self._cancel_flags[queue_id] = asyncio.Event()
       return self._cancel_flags[queue_id]

   def cleanup_operation_state(self, queue_id: str):
       """Clean up lock and cancel flag after operation completes."""
       self._operation_locks.pop(queue_id, None)
       self._cancel_flags.pop(queue_id, None)
   ```

3. **Wrap callback handlers with lock acquisition**:
   - In `telegram_callbacks.py`, `complete_queue_action()` should acquire the lock:
     ```python
     lock = self.service.get_operation_lock(queue_id)
     if lock.locked():
         await query.answer("⏳ Already processing this item...", show_alert=False)
         return
     async with lock:
         # existing logic...
         self.service.cleanup_operation_state(queue_id)
     ```
   - In `telegram_autopost.py`, `handle_autopost()` should acquire the lock AND check cancellation:
     ```python
     lock = self.service.get_operation_lock(queue_id)
     if lock.locked():
         await query.answer("⏳ Already processing...", show_alert=False)
         return
     cancel_flag = self.service.get_cancel_flag(queue_id)
     cancel_flag.clear()
     async with lock:
         # After Cloudinary upload, check cancellation:
         if cancel_flag.is_set():
             # Clean up Cloudinary upload
             await query.edit_message_caption(caption="❌ Auto-post cancelled")
             return
         # Before Instagram API call, check again:
         if cancel_flag.is_set():
             return
         # ... rest of existing logic
         self.service.cleanup_operation_state(queue_id)
     ```

4. **Terminal actions cancel pending auto-posts**:
   - In `handle_posted()`, `handle_skipped()`, and `handle_rejected()` — before acquiring the lock, set the cancel flag:
     ```python
     cancel_flag = self.service.get_cancel_flag(queue_id)
     cancel_flag.set()  # Signal any pending autopost to abort
     ```

5. **Write tests** in `tests/src/services/test_telegram_callbacks.py`:
   - Test that double-clicking "Posted" doesn't create duplicate history entries
   - Test that clicking "Posted" while auto-post is pending cancels the auto-post
   - Test that the lock is cleaned up after operation completes
   - Test the "⏳ Already processing..." feedback message

6. **Update documentation**:
   - Mark the backlog item in `00_MASTER_ROADMAP.md` as COMPLETE
   - Add a CHANGELOG entry under `[Unreleased]` → `### Fixed`
   - Update `documentation/guides/TEST_COVERAGE.md` if new tests are added

**Important safety notes:**
- Do NOT run `python -m src.main` or any posting commands
- Run `pytest` to verify all tests pass
- Run `ruff check src/ tests/ && ruff format --check src/ tests/` before committing

### Final Steps

After all three tasks are done:
1. Run `source venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/ && pytest` to verify everything passes
2. Commit with a descriptive message
3. Push to the working branch
