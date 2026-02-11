# Update Outdated Dependencies

✅ COMPLETE | Completed: 2026-02-10 | PR: #36

| Field | Value |
|---|---|
| **PR Title** | `chore: update outdated dependencies` |
| **Risk Level** | Medium |
| **Effort** | Medium (3-4 hours) |
| **Dependencies** | None (can run in parallel with other phases) |
| **Blocks** | None |
| **Files Modified** | `requirements.txt` |

---

## Problem Description

The project's `requirements.txt` pins exact versions for most packages, but many of those pins are 1-2+ years stale. Outdated dependencies accumulate security vulnerabilities, miss bug fixes, and make future upgrades harder (the bigger the jump, the more likely something breaks).

The current `requirements.txt` (as of 2026-02-10):

```
# Core
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.13.0

# Telegram
python-telegram-bot==20.7
httpx==0.25.2

# Image Processing
Pillow==10.1.0

# CLI
click==8.1.7
rich==13.7.0

# Utilities
python-dateutil==2.8.2

# Cloud Storage (Phase 2)
cloudinary>=1.36.0

# Security (Phase 2)
cryptography>=41.0.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
```

Note that `cloudinary` and `cryptography` use `>=` (minimum version pins) rather than `==` (exact pins). These will already be at their latest compatible version in the installed environment. The focus here is on the `==`-pinned packages.

---

## Step-by-Step Implementation

### Overview: Three Tiers

Updates are organized into three tiers based on risk. Complete each tier fully (install, test, commit) before moving to the next.

| Tier | Risk | What | Count |
|---|---|---|---|
| **Tier 1** | Low | Patch version updates (bug fixes only) | 4 packages |
| **Tier 2** | Medium | Minor version updates (new features, backward-compatible) | 10 packages |
| **Tier 3** | High | Major version updates (potential breaking changes) | 6 packages |

---

### Tier 1: Patch Updates (Low Risk)

These are bug-fix-only releases. The API surface is unchanged.

**Packages:**

| Package | Current | Target | Change |
|---|---|---|---|
| `psycopg2-binary` | 2.9.9 | 2.9.11 | Patch (bug fixes) |
| `python-dateutil` | 2.8.2 | 2.9.0.post0 | Minor (but dateutil is very stable) |

> **Note**: `anyio`, `greenlet`, `coverage`, `pydantic_core` are transitive dependencies -- they are not pinned in `requirements.txt` and will update automatically when their parent packages are updated. Only update packages that are explicitly listed in `requirements.txt`.

**Step 1a: Update `requirements.txt`**

**Before:**
```
psycopg2-binary==2.9.9
```

**After:**
```
psycopg2-binary==2.9.11
```

**Before:**
```
python-dateutil==2.8.2
```

**After:**
```
python-dateutil==2.9.0.post0
```

**Step 1b: Install and test**

```bash
source venv/bin/activate
pip install -r requirements.txt

# Run full test suite
pytest

# Quick smoke test of database connection
storyline-cli check-health
```

**Step 1c: If something breaks**

```bash
# Rollback by reverting the version pin in requirements.txt
# Then reinstall
pip install psycopg2-binary==2.9.9 python-dateutil==2.8.2
```

**Step 1d: Commit**

```bash
git add requirements.txt
git commit -m "chore: update patch dependencies (psycopg2-binary, python-dateutil)"
```

---

### Tier 2: Minor Version Updates (Medium Risk)

These are backward-compatible releases but may include behavior changes. Read the upgrade notes for each.

**Packages:**

| Package | Current | Target | Change | Notes |
|---|---|---|---|---|
| `click` | 8.1.7 | 8.3.1 | Minor | CLI framework -- test all CLI commands |
| `httpx` | 0.25.2 | 0.28.1 | Minor | HTTP client used by Telegram bot and Instagram API |
| `pydantic` | 2.5.0 | 2.12.5 | Minor | Data validation -- test settings loading |
| `pydantic-settings` | 2.1.0 | 2.12.0 | Minor | Settings management -- must match pydantic version |
| `SQLAlchemy` | 2.0.23 | 2.0.46 | Patch | Database ORM -- test all repository operations |
| `rich` | 13.7.0 | 14.3.2 | Major (rich) | CLI formatting -- visual changes only |
| `python-dotenv` | 1.0.0 | 1.2.1 | Minor | .env loading -- test settings initialization |
| `alembic` | 1.13.0 | 1.18.4 | Minor | DB migrations -- not actively used (manual SQL) |

> **Important**: `pydantic` and `pydantic-settings` MUST be updated together. They share the `pydantic_core` dependency and version mismatches will cause import errors.

**Step 2a: Update `requirements.txt`**

Apply all Tier 2 changes at once:

**Before:**
```
# Core
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.23
alembic==1.13.0

# Telegram
httpx==0.25.2

# CLI
click==8.1.7
rich==13.7.0
```

**After:**
```
# Core
python-dotenv==1.2.1
pydantic==2.12.5
pydantic-settings==2.12.0

# Database
sqlalchemy==2.0.46
alembic==1.18.4

# Telegram
httpx==0.28.1

# CLI
click==8.3.1
rich==14.3.2
```

**Step 2b: Install and test**

```bash
source venv/bin/activate
pip install -r requirements.txt

# 1. Full test suite
pytest

# 2. Test settings loading (pydantic/pydantic-settings)
python -c "from src.config.settings import settings; print(settings.DB_HOST)"

# 3. Test CLI (click/rich)
storyline-cli check-health
storyline-cli list-categories
storyline-cli instagram-status

# 4. Test database operations (SQLAlchemy)
storyline-cli list-queue
storyline-cli list-media
```

**Known issues to watch for:**

- **pydantic 2.5 -> 2.12**: The `model_config` API is stable across 2.x but deprecated validator syntax may emit warnings. Check for `DeprecationWarning` in test output.
- **httpx 0.25 -> 0.28**: The `AsyncClient` API is stable but some timeout defaults changed. If Telegram bot or Instagram API calls start timing out, check `httpx.Timeout` configuration.
- **rich 13 -> 14**: Major version but the `Console`, `Table`, and `Panel` APIs used in CLI commands are stable. Visual output formatting may change slightly.

**Step 2c: If something breaks**

Roll back individual packages to isolate the issue:

```bash
# If pydantic breaks settings:
pip install pydantic==2.5.0 pydantic-settings==2.1.0

# If httpx breaks API calls:
pip install httpx==0.25.2

# If click breaks CLI:
pip install click==8.1.7

# If SQLAlchemy breaks repositories:
pip install sqlalchemy==2.0.23
```

**Step 2d: Commit**

```bash
git add requirements.txt
git commit -m "chore: update minor dependencies (pydantic, httpx, click, SQLAlchemy, rich, alembic)"
```

---

### Tier 3: Major Version Updates (High Risk)

These are multi-major-version jumps that are likely to have breaking changes. Each package should be updated and tested individually.

**Packages:**

| Package | Current | Target | Jump | Risk |
|---|---|---|---|---|
| `Pillow` | 10.1.0 | 12.1.0 | 2 major | Medium -- image processing API may change |
| `python-telegram-bot` | 20.7 | 22.6 | 2 major | **HIGHEST RISK** -- bot framework |
| `pytest` | 7.4.3 | 9.0.2 | 2 major | Medium -- test runner |
| `pytest-asyncio` | 0.21.1 | 1.3.0 | 1 major | Medium -- async test support |
| `pytest-cov` | 4.1.0 | 7.0.0 | 3 major | Low -- coverage reporting |
| `pytest-mock` | 3.12.0 | 3.15.1 | Patch | Low -- mocking utilities |

#### Step 3a: Update `pytest-mock` (lowest risk, do first)

**Before:**
```
pytest-mock==3.12.0
```

**After:**
```
pytest-mock==3.15.1
```

```bash
pip install pytest-mock==3.15.1
pytest
```

#### Step 3b: Update `pytest-cov`

**Before:**
```
pytest-cov==4.1.0
```

**After:**
```
pytest-cov==7.0.0
```

```bash
pip install pytest-cov==7.0.0
pytest --cov=src --cov-report=term-missing
```

**Watch for**: Changes to coverage configuration format. Check `pyproject.toml` or `setup.cfg` for `[tool:pytest]` coverage settings.

#### Step 3c: Update `pytest` and `pytest-asyncio` together

These must be updated together because `pytest-asyncio` depends on a specific range of `pytest` versions.

**Before:**
```
pytest==7.4.3
pytest-asyncio==0.21.1
```

**After:**
```
pytest==9.0.2
pytest-asyncio==1.3.0
```

```bash
pip install pytest==9.0.2 pytest-asyncio==1.3.0
pytest
```

**Known breaking changes to watch for:**

- **pytest 8.0+**: Changed how `--import-mode` works. If tests fail with import errors, add `--import-mode=importlib` to pytest args.
- **pytest-asyncio 0.21 -> 1.3**: The `asyncio_mode` configuration changed. You may need to add `asyncio_mode = "auto"` to `pyproject.toml` or `pytest.ini`. If async tests fail with `"coroutine was never awaited"` warnings, this is the likely cause.
  - The `@pytest.mark.asyncio` decorator behavior may have changed. Check if tests need `@pytest.mark.asyncio(loop_scope="function")` or similar.

**If tests break:**
```bash
# Rollback both
pip install pytest==7.4.3 pytest-asyncio==0.21.1
```

#### Step 3d: Update `Pillow`

**Before:**
```
Pillow==10.1.0
```

**After:**
```
Pillow==12.1.0
```

```bash
pip install Pillow==12.1.0

# Test image processing specifically
pytest tests/src/utils/test_image_processing.py -v

# Test image validation CLI
storyline-cli validate-image /path/to/any/test-image.jpg
```

**Known breaking changes:**

- **Pillow 10 -> 11**: Some deprecated APIs were removed. Check if the code uses `Image.ANTIALIAS` (removed in Pillow 10, replaced with `Image.LANCZOS`). Search for usage:
  ```bash
  grep -rn "ANTIALIAS" src/
  ```
- **Pillow 11 -> 12**: Further deprecation removals. Check `ImageDraw` and `ImageFont` usage if applicable.

**If image processing breaks:**
```bash
pip install Pillow==10.1.0
```

#### Step 3e: Update `python-telegram-bot` (DO THIS LAST)

> **CRITICAL WARNING**: This is the highest-risk update in the entire plan. `python-telegram-bot` v20 -> v22 spans two major versions and the library has historically made significant API changes between major versions. **Budget extra time for this update.** It may require code changes in `src/services/core/telegram_service.py` and all handler modules.

**Before:**
```
python-telegram-bot==20.7
```

**After:**
```
python-telegram-bot==22.6
```

**Before attempting this update:**

1. Read the migration guides:
   - v20 -> v21: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Transition-guide-to-Version-21.0
   - v21 -> v22: Check the project's CHANGES.rst or GitHub releases

2. Create a feature branch specifically for this update:
   ```bash
   git checkout -b chore/update-telegram-bot
   ```

3. Search for API patterns that commonly change between major versions:
   ```bash
   # Check how the bot is initialized
   grep -rn "Application\|ApplicationBuilder\|Updater" src/services/core/telegram_service.py

   # Check callback query handling
   grep -rn "CallbackQueryHandler\|CommandHandler" src/services/core/telegram_service.py

   # Check message sending patterns
   grep -rn "send_photo\|send_message\|edit_message" src/services/core/
   ```

4. Install and test:
   ```bash
   pip install python-telegram-bot==22.6

   # Run all Telegram-related tests
   pytest tests/src/services/test_telegram_service.py -v
   pytest tests/src/services/test_telegram_callbacks.py -v
   pytest tests/src/services/test_telegram_commands.py -v
   pytest tests/src/services/test_telegram_settings.py -v
   pytest tests/src/services/test_telegram_accounts.py -v
   pytest tests/src/services/test_telegram_autopost.py -v

   # Run full suite
   pytest
   ```

**Common breaking changes in python-telegram-bot major versions:**

- `Updater` class may be restructured or removed (replaced by `Application`)
- `CallbackContext` parameter types may change
- `InlineKeyboardButton` / `InlineKeyboardMarkup` API may have parameter changes
- Async patterns may change (e.g., how `await` is used with bot methods)
- Error handling classes may be renamed or restructured

**If the bot breaks (likely):**

```bash
# Immediate rollback
pip install python-telegram-bot==20.7

# Then plan code changes as a separate PR
```

**Recommendation**: If `python-telegram-bot` 22.6 requires code changes, split this into its own PR with the code changes. Do NOT bundle code changes with the other dependency updates.

---

### Final `requirements.txt` (After All Tiers)

```
# Core
python-dotenv==1.2.1
pydantic==2.12.5
pydantic-settings==2.12.0

# Database
sqlalchemy==2.0.46
psycopg2-binary==2.9.11
alembic==1.18.4

# Telegram
python-telegram-bot==22.6
httpx==0.28.1

# Image Processing
Pillow==12.1.0

# CLI
click==8.3.1
rich==14.3.2

# Utilities
python-dateutil==2.9.0.post0

# Cloud Storage (Phase 2)
cloudinary>=1.36.0

# Security (Phase 2)
cryptography>=41.0.0

# Testing
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
pytest-mock==3.15.1
```

---

## Verification Checklist

After each tier:

```bash
# 1. All tests pass
pytest

# 2. Linting still passes
ruff check src/ tests/

# 3. CLI commands work
storyline-cli check-health
storyline-cli list-queue
storyline-cli instagram-status

# 4. No deprecation warnings in test output
pytest -W error::DeprecationWarning 2>&1 | head -20
```

After all tiers:

```bash
# 5. Verify installed versions match requirements.txt
pip freeze | grep -E "(pydantic|sqlalchemy|click|httpx|Pillow|telegram|pytest)"

# 6. Run full test suite with coverage
pytest --cov=src --cov-report=term-missing
```

---

## What NOT To Do

1. **Do NOT update all packages at once.** Update tier by tier, test after each tier, and commit after each tier. If you update everything at once and tests break, you will not know which package caused the failure.

2. **Do NOT update `python-telegram-bot` at the same time as other packages.** This is the highest-risk update and must be isolated. If it requires code changes, those changes go in a separate PR.

3. **Do NOT update transitive dependencies** (packages not listed in `requirements.txt`). They will update automatically when their parent packages are updated. Adding explicit pins for transitive dependencies creates maintenance burden and version conflicts.

4. **Do NOT remove the `>=` pins** on `cloudinary` and `cryptography`. These are intentionally using minimum-version pins because their exact version does not matter -- any compatible version works.

5. **Do NOT run `pip install --upgrade` without specifying versions.** Always pin to a specific version in `requirements.txt` and install from the file. Unpinned upgrades can pull in incompatible transitive dependencies.

6. **Do NOT skip testing after Tier 3 updates.** Major version jumps can break things in subtle ways (e.g., a method returns a different type, a default parameter value changed). Run the full test suite, not just the tests you think are relevant.

7. **Do NOT update on the production Raspberry Pi first.** Update locally, verify all tests pass, merge the PR, then update the Pi.
