# Phase 05: Standardize Dependency Pinning and Add Lock File

## Header

| Field | Value |
|-------|-------|
| **PR Title** | `chore: standardize dependency pinning and add lock file` |
| **Severity** | LOW |
| **Effort** | Low-Medium (1-2 hours) |
| **Risk** | Low |
| **Dependencies** | Phase 02 (dependency updates) must be completed first |
| **Unlocks** | None |

### Files Modified

| File | Action |
|------|--------|
| `requirements.txt` | Modified -- pin all `>=` packages to exact `==` versions |
| `setup.py` | Modified -- keep `>=` floor pins (these are correct for library-style metadata) |
| `Makefile` | Modified -- add `lock` and `upgrade` targets |
| `.github/workflows/ci.yml` | Modified -- add lock file verification step |

### Files Created

| File | Purpose |
|------|---------|
| `requirements.lock` | Auto-generated fully-resolved lock file from `pip-compile` |
| `requirements-dev.in` | Source file for dev/test dependencies (input to `pip-compile`) |
| `requirements-dev.lock` | Auto-generated lock file for dev/test dependencies |

---

## Context

### Finding Addressed

**Finding #14 (LOW)**: Inconsistent version pinning in `requirements.txt` -- some packages use exact pins (`==`), others use floor pins (`>=`) with no upper bound. No lock file exists. This creates reproducibility and security risks: floor-pinned packages can silently upgrade to vulnerable versions on fresh installs, and different environments (developer laptops, CI, Railway production) may resolve to different dependency trees.

### Why This Matters

The current `requirements.txt` has a split personality:

- **13 packages** use exact pins (`==`): `python-dotenv==1.2.1`, `pydantic==2.12.5`, `sqlalchemy==2.0.46`, etc.
- **7 packages** use floor pins (`>=`): `cryptography>=41.0.0`, `fastapi>=0.109.0`, `uvicorn>=0.27.0`, `cloudinary>=1.36.0`, `google-api-python-client>=2.100.0`, `google-auth>=2.23.0`, `google-auth-oauthlib>=1.1.0`

The floor-pinned packages are the exact ones that caused the vulnerability findings in this audit. For example, `cryptography>=41.0.0` resolved to 46.0.3, which has two HIGH-severity CVEs. After Phase 02 updates versions, this phase ensures the *pinning strategy* prevents the same class of problem from recurring.

Additionally, there is no lock file. Even with exact pins in `requirements.txt`, transitive dependencies (the packages your packages depend on) are completely unpinned. A transitive dependency like `starlette` (pulled in by `fastapi`) can silently change between installs.

---

## Dependencies

- **Phase 02 (dependency updates) must be completed first.** Phase 02 updates packages to their patched versions. This phase then pins those updated versions exactly and generates a lock file. Running this phase first would pin the *current* vulnerable versions, and Phase 02 would then have to re-pin everything -- causing unnecessary merge conflicts.

---

## Detailed Implementation Plan

### Strategy

1. **`requirements.txt`**: Pin ALL production dependencies to exact versions (`==`). This file serves as the *direct dependency declaration* with human-chosen versions.
2. **`requirements.lock`**: Generate via `pip-compile` from `requirements.txt`. This captures the full transitive dependency tree with exact versions and hashes.
3. **`setup.py`**: Keep `>=` floor pins. This file defines the *installable package* metadata and should express minimum compatibility, not exact pins (standard Python packaging convention).
4. **`requirements-dev.in` / `requirements-dev.lock`**: Separate dev/test dependencies into their own input/lock file pair, keeping production lean.
5. **CI verification**: Add a step that fails if `requirements.lock` is stale (out of sync with `requirements.txt`).

### Step 1: Install pip-tools locally

`pip-tools` provides `pip-compile` (generates lock files) and `pip-sync` (installs exactly what the lock file says). Install it in the development venv:

```bash
pip install pip-tools
```

This is a development-only tool. It does NOT need to be in `requirements.txt` or deployed to production.

### Step 2: Pin all floor-pinned packages in requirements.txt

Open `requirements.txt` and change every `>=` to `==` with the version that Phase 02 installed. The exact versions below assume Phase 02 has already run -- **verify the installed versions after Phase 02 completes** by running `pip freeze | grep -i <package>` for each one.

**Current file (`requirements.txt`):**

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
Pillow==12.1.1

# CLI
click==8.3.1
rich==14.3.2

# Utilities
python-dateutil==2.9.0.post0

# Cloud Storage (Phase 2)
cloudinary>=1.36.0

# Google Drive (Cloud Media Phase 02)
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0

# API Server (Phase 04 OAuth)
fastapi>=0.109.0
uvicorn>=0.27.0

# Security (Phase 2)
cryptography>=41.0.0

# Testing
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
pytest-mock==3.15.1
```

**Target file (`requirements.txt`) after this phase:**

Replace every `>=` pin with `==` using the actual installed version from Phase 02. The implementer must run `pip freeze` after Phase 02 and use those exact versions. The pattern for each line is shown below -- substitute `<VERSION>` with the actual installed version:

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
Pillow==12.1.1

# CLI
click==8.3.1
rich==14.3.2

# Utilities
python-dateutil==2.9.0.post0

# Cloud Storage (Phase 2)
cloudinary==<VERSION>

# Google Drive (Cloud Media Phase 02)
google-api-python-client==<VERSION>
google-auth==<VERSION>
google-auth-oauthlib==<VERSION>

# API Server (Phase 04 OAuth)
fastapi==<VERSION>
uvicorn==<VERSION>

# Security (Phase 2)
cryptography==<VERSION>
```

**Concrete example** (using versions from the research file -- these will change after Phase 02 updates):

| Line | Before | After (example) |
|------|--------|-----------------|
| 26 | `cloudinary>=1.36.0` | `cloudinary==1.36.0` (or whatever `pip freeze` shows) |
| 29 | `google-api-python-client>=2.100.0` | `google-api-python-client==2.157.0` (verify) |
| 30 | `google-auth>=2.23.0` | `google-auth==2.38.0` (verify) |
| 31 | `google-auth-oauthlib>=1.1.0` | `google-auth-oauthlib==1.2.1` (verify) |
| 34 | `fastapi>=0.109.0` | `fastapi==0.135.3` (verify -- Phase 02 updates this) |
| 35 | `uvicorn>=0.27.0` | `uvicorn==0.44.0` (verify -- Phase 02 updates this) |
| 38 | `cryptography>=41.0.0` | `cryptography==46.0.7` (verify -- Phase 02 updates this) |

**Important**: Do NOT guess versions. Run `pip freeze | grep -i <package>` in the venv after Phase 02 is complete and use the exact output.

Also remove the testing dependencies from `requirements.txt` -- they will move to `requirements-dev.in` (Step 3). Delete these four lines:

```
# Testing
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
pytest-mock==3.15.1
```

### Step 3: Create requirements-dev.in for dev/test dependencies

Create a new file `requirements-dev.in` at the project root:

```
# requirements-dev.in
# Dev/test dependencies -- compiled to requirements-dev.lock via:
#   pip-compile requirements-dev.in -o requirements-dev.lock
#
# These are NOT installed in production (Railway).

-c requirements.lock  # Constrain to same versions as production lock

# Testing
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
pytest-mock==3.15.1

# Linting (matches CI)
ruff

# Security scanning
pip-audit
bandit
```

The `-c requirements.lock` constraint line ensures dev dependencies resolve transitive packages to the same versions as production, preventing "works on my machine" issues.

### Step 4: Generate lock files

Run these commands from the project root with the venv active:

```bash
# Generate production lock file from requirements.txt
pip-compile requirements.txt -o requirements.lock --generate-hashes --no-header

# Generate dev lock file from requirements-dev.in
pip-compile requirements-dev.in -o requirements-dev.lock --generate-hashes --no-header
```

The `--generate-hashes` flag adds SHA256 hashes for every package, enabling pip to verify package integrity on install (supply-chain protection).

The `--no-header` flag omits the auto-generated comment header that includes the pip-compile version and timestamp, reducing noisy diffs on regeneration.

**Expected output**: `requirements.lock` will contain every direct and transitive dependency with exact versions and hashes. For example:

```
# This file is autogenerated by pip-compile with Python 3.10
alembic==1.18.4 \
    --hash=sha256:abc123...
cryptography==46.0.7 \
    --hash=sha256:def456...
fastapi==0.135.3 \
    --hash=sha256:ghi789...
starlette==1.0.0 \
    --hash=sha256:jkl012...
# ... (all transitive deps pinned)
```

### Step 5: Update setup.py -- keep floor pins

`setup.py` already uses `>=` floor pins (lines 11-30). This is correct and should NOT be changed. The `setup.py` `install_requires` defines what the *package* needs to install when someone runs `pip install -e .` -- it should express minimum compatibility, not exact pins. The lock file handles exactness.

No changes to `setup.py` in this phase.

**Wait -- one small update**: add a comment to `setup.py` clarifying the pinning strategy so future contributors understand the intentional difference:

In `setup.py`, add a comment above `install_requires`:

```python
setup(
    name="storyline-ai",
    version=__version__,
    description="Instagram Story Automation System with Telegram Integration",
    author="Your Name",
    packages=find_packages(),
    # Floor pins (>=) are intentional here -- setup.py defines minimum
    # compatibility for the installable package. Exact versions are pinned
    # in requirements.txt and locked in requirements.lock.
    install_requires=[
```

The exact edit in `setup.py`:

**Before (line 11):**
```python
    install_requires=[
```

**After (lines 11-14):**
```python
    # Floor pins (>=) are intentional here -- setup.py defines minimum
    # compatibility for the installable package. Exact versions are pinned
    # in requirements.txt and locked in requirements.lock.
    install_requires=[
```

### Step 6: Update Makefile with lock and upgrade targets

Add these targets to `Makefile` after the existing `install-dev` target (after line 57):

```makefile
lock: ## Regenerate dependency lock files (run after changing requirements.txt)
	@echo "$(GREEN)Generating lock files...$(NC)"
	pip-compile requirements.txt -o requirements.lock --generate-hashes --no-header
	pip-compile requirements-dev.in -o requirements-dev.lock --generate-hashes --no-header
	@echo "$(GREEN)✓ Lock files regenerated$(NC)"

upgrade: ## Upgrade all dependencies and regenerate lock files
	@echo "$(GREEN)Upgrading dependencies...$(NC)"
	pip-compile requirements.txt -o requirements.lock --generate-hashes --no-header --upgrade
	pip-compile requirements-dev.in -o requirements-dev.lock --generate-hashes --no-header --upgrade
	@echo "$(GREEN)✓ Dependencies upgraded and lock files regenerated$(NC)"
	@echo "$(YELLOW)→ Review changes in requirements.lock and run tests before committing$(NC)"

sync: ## Install exact versions from lock files (reproducible install)
	@echo "$(GREEN)Syncing dependencies from lock files...$(NC)"
	pip-sync requirements.lock requirements-dev.lock
	pip install -e .
	@echo "$(GREEN)✓ Dependencies synced$(NC)"
```

Also update the `.PHONY` line at the top of the Makefile:

**Before (line 1):**
```makefile
.PHONY: help install test clean create-db drop-db reset-db init-db setup-db check-health run dev
```

**After (line 1):**
```makefile
.PHONY: help install test clean create-db drop-db reset-db init-db setup-db check-health run dev lock upgrade sync
```

And update the `install` target to use the lock file:

**Before (lines 47-51):**
```makefile
install: ## Install Python dependencies and CLI
	@echo "$(GREEN)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	pip install -e .
	@echo "$(GREEN)✓ Installation complete$(NC)"
```

**After:**
```makefile
install: ## Install Python dependencies and CLI
	@echo "$(GREEN)Installing dependencies...$(NC)"
	@if [ -f requirements.lock ]; then \
		pip install -r requirements.lock; \
	else \
		pip install -r requirements.txt; \
	fi
	pip install -e .
	@echo "$(GREEN)✓ Installation complete$(NC)"
```

### Step 7: Update CI workflow to verify lock file freshness

Add a new step to the `test` job in `.github/workflows/ci.yml`, after the "Install dependencies" step (after line 73). This step verifies that `requirements.lock` is in sync with `requirements.txt`:

**Insert after line 73 (`pip install -r requirements.txt`):**

Replace the existing "Install dependencies" step:

**Before (lines 69-73):**
```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest-cov
```

**After:**
```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.lock
          pip install pip-tools pytest-cov

      - name: Verify lock file is up-to-date
        run: |
          pip-compile requirements.txt -o /tmp/requirements-check.lock --generate-hashes --no-header
          if ! diff -q requirements.lock /tmp/requirements-check.lock > /dev/null 2>&1; then
            echo "::error::requirements.lock is out of date. Run 'make lock' and commit the result."
            diff requirements.lock /tmp/requirements-check.lock || true
            exit 1
          fi
          echo "requirements.lock is up-to-date"
```

Also update the `security` job to install from the lock file:

**Before (lines 117-119):**
```yaml
      - name: Install dependencies
        run: |
          pip install pip-audit bandit
```

**After:**
```yaml
      - name: Install dependencies
        run: |
          pip install pip-audit bandit
          pip install -r requirements.lock
```

This ensures `pip-audit` scans the exact locked versions, not just what `requirements.txt` declares.

### Step 8: Add lock files to .gitignore exceptions

Check if `.gitignore` exists and ensure lock files are NOT ignored. Lock files must be committed to the repository -- they are the whole point of this change.

If `.gitignore` contains `*.lock` or similar patterns, add explicit exceptions:

```
# Dependency lock files (DO commit these)
!requirements.lock
!requirements-dev.lock
```

If `.gitignore` does not ignore `*.lock`, no change is needed.

---

## Test Plan

### Automated Tests

No new test files are needed. This phase changes dependency management tooling, not application code. Existing tests validate that the application works correctly with the resolved dependencies.

### Verification Commands

Run these commands in order after making all changes:

```bash
# 1. Verify requirements.txt has no >= pins remaining
grep '>=' requirements.txt
# Expected: NO output (all >= should be converted to ==)

# 2. Generate lock files
pip-compile requirements.txt -o requirements.lock --generate-hashes --no-header
pip-compile requirements-dev.in -o requirements-dev.lock --generate-hashes --no-header

# 3. Verify lock files were created and contain hashes
head -20 requirements.lock
# Expected: packages with --hash=sha256:... lines

# 4. Verify pip-sync works (installs exact versions)
pip-sync requirements.lock requirements-dev.lock
pip install -e .

# 5. Run full test suite to confirm nothing broke
pytest tests/ -v

# 6. Run linting
ruff check src/ tests/
ruff format --check src/ tests/

# 7. Verify the Makefile targets work
make lock
make sync

# 8. Verify CI lock freshness check would pass
pip-compile requirements.txt -o /tmp/requirements-check.lock --generate-hashes --no-header
diff requirements.lock /tmp/requirements-check.lock
# Expected: no differences
```

### Manual Verification

1. **Fresh install test**: Create a new venv, install from `requirements.lock`, and run tests:
   ```bash
   python -m venv /tmp/test-venv
   /tmp/test-venv/bin/pip install -r requirements.lock
   /tmp/test-venv/bin/pip install -e .
   /tmp/test-venv/bin/pytest tests/ -v
   ```

2. **Version drift check**: Compare `pip freeze` output against `requirements.lock` to confirm they match exactly.

---

## Documentation Updates

### CLAUDE.md

No changes needed. The existing development setup commands (`pip install -r requirements.txt && pip install -e .`) will continue to work. The lock file is an additional layer, not a replacement.

### Inline Comments

- Add comment to `setup.py` explaining the floor pin strategy (see Step 5 above).
- Add header comment to `requirements-dev.in` explaining its purpose and how to compile it (included in Step 3 above).

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- Standardized all dependency pins in `requirements.txt` to exact versions (`==`)
- CI now installs from `requirements.lock` for reproducible builds

### Added
- `requirements.lock` -- fully resolved dependency lock file with integrity hashes
- `requirements-dev.in` / `requirements-dev.lock` -- separated dev/test dependencies
- Makefile targets: `make lock`, `make upgrade`, `make sync`
- CI step to verify lock file freshness
```

---

## Stress Testing and Edge Cases

### Edge Case: pip-compile version differences

Different versions of `pip-compile` can produce slightly different lock file output (ordering, hash format). Pin the `pip-tools` version in CI:

```yaml
pip install pip-tools==7.4.1 pytest-cov
```

Use whatever version is current at implementation time, but pin it exactly.

### Edge Case: Platform-specific dependencies

Some packages (e.g., `psycopg2-binary`) have platform-specific wheels. The `--generate-hashes` flag in `pip-compile` includes hashes for ALL available platforms by default, so this should work across macOS (developer) and Linux (CI/Railway) without issues.

If a hash mismatch occurs on a specific platform, use `--allow-unsafe` flag as a last resort, but first investigate whether the package publishes wheels for both platforms.

### Edge Case: Railway deployment

Railway installs dependencies via `pip install -r requirements.txt` (the default Python buildpack behavior). After this change, Railway should be configured to install from `requirements.lock` instead. Check the Railway service settings or add a `railway.toml` / `Procfile` / `nixpacks.toml` that specifies:

```toml
# nixpacks.toml (if Railway uses nixpacks)
[phases.setup]
cmds = ["pip install -r requirements.lock"]
```

If Railway does not support custom install commands, `requirements.txt` with exact `==` pins still provides strong reproducibility -- the lock file adds transitive pinning and hash verification on top.

### Edge Case: Dependabot / Renovate

If automated dependency update tools are added in the future, they should be configured to update `requirements.txt` (the source of truth) and then regenerate the lock file. The CI freshness check will catch any PRs that update `requirements.txt` without regenerating the lock.

---

## Verification Checklist

- [ ] All `>=` pins in `requirements.txt` converted to `==`
- [ ] Test dependencies removed from `requirements.txt` (moved to `requirements-dev.in`)
- [ ] `requirements-dev.in` created with test/lint/security deps
- [ ] `requirements.lock` generated with hashes
- [ ] `requirements-dev.lock` generated with hashes
- [ ] `setup.py` unchanged except for explanatory comment
- [ ] Makefile has `lock`, `upgrade`, and `sync` targets
- [ ] Makefile `.PHONY` updated
- [ ] Makefile `install` target uses lock file when available
- [ ] CI `test` job installs from `requirements.lock`
- [ ] CI `test` job has lock file freshness check
- [ ] CI `security` job installs from `requirements.lock`
- [ ] `pip-tools` version pinned in CI
- [ ] `pytest` passes with no failures
- [ ] `ruff check` and `ruff format --check` pass
- [ ] CHANGELOG.md updated
- [ ] Lock files committed to repository (not in `.gitignore`)
- [ ] Fresh venv install from lock file succeeds

---

## What NOT To Do

### Do NOT pin to the current vulnerable versions

If you run this phase before Phase 02, you will pin `cryptography==46.0.3` (vulnerable) and `starlette==0.52.1` (vulnerable). Always complete Phase 02 first, then pin the updated versions.

### Do NOT remove flexibility from setup.py

`setup.py` uses `>=` floor pins intentionally. These define the *minimum* version the package is compatible with. Changing these to `==` would break `pip install -e .` for anyone with a different (but compatible) version already installed. The lock file handles exact pinning; `setup.py` handles compatibility.

### Do NOT use pip freeze as the lock file

Running `pip freeze > requirements.lock` is tempting but wrong. `pip freeze` does not include hashes, does not distinguish direct from transitive dependencies, and includes development tools (like `pip-tools` itself) in the output. Use `pip-compile` exclusively.

### Do NOT add pip-tools to requirements.txt

`pip-tools` is a development/CI tool, not a production dependency. It belongs in the CI workflow and developer setup instructions, not in the production dependency list.

### Do NOT use `requirements.lock` as the sole source of truth

`requirements.txt` remains the human-edited file where you declare direct dependencies and their versions. `requirements.lock` is a *derived artifact* generated from `requirements.txt`. When upgrading a package, edit `requirements.txt` first, then run `make lock` to regenerate.

### Do NOT ignore lock file diffs in code review

Lock file regeneration can produce large diffs. Reviewers should verify:
1. The direct dependency change in `requirements.txt` is intentional
2. No unexpected transitive dependencies were added or removed
3. No packages were downgraded unexpectedly

### Do NOT skip the CI freshness check

The freshness check is the enforcement mechanism. Without it, developers can update `requirements.txt` and forget to regenerate the lock file, silently re-introducing the reproducibility problem this phase solves.
