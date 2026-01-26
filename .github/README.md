# GitHub Workflows

This directory contains GitHub Actions workflows for CI.

---

## Current Setup

### ✅ Continuous Integration (Automated)

**File**: `ci.yml`

Runs automatically on every push and pull request:
- **Lint** - Code style checks with ruff
- **Test** - Unit and integration tests with pytest
- **Security** - Vulnerability scanning with pip-audit and bandit
- **Changelog** - Verify CHANGELOG.md is updated

All jobs run on **GitHub's cloud runners** (`ubuntu-latest`) - safe for public repositories.

### ⚠️ Deployment (Manual Only)

**File**: `deploy.yml` - Disabled by default (requires Tailscale setup)

For security reasons, deployment is **manual**:

```bash
./scripts/deploy.sh
```

This ensures your Pi and credentials remain secure.

---

## Why Manual Deployment?

**Public repositories cannot safely use self-hosted runners.**

Malicious users can:
- Submit PRs with harmful code
- Execute code on your Pi through workflows
- Steal secrets and access your local network

See: [GitHub's security documentation](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security)

---

## Deployment Options

### Option 1: Manual Deployment (Current - Recommended)

```bash
./scripts/deploy.sh
```

- ✅ Safe for public repos
- ✅ Simple and fast
- ✅ No external dependencies
- ⚠️ Requires SSH access to Pi

### Option 2: Tailscale VPN (Advanced)

For automated deployment with security:

See: [documentation/guides/github-actions-tailscale.md](../documentation/guides/github-actions-tailscale.md)

- ✅ Safe for public repos
- ✅ Automated on every push
- ⚠️ Requires Tailscale account and setup

---

## CI Failures

If CI is failing, common issues:

### Lint Errors
```bash
# Fix automatically
ruff format src/ cli/

# Check for issues
ruff check src/ cli/
```

### Test Failures
```bash
# Run tests locally
pytest tests/ -v

# Run specific test
pytest tests/path/to/test.py::test_name -v
```

### Missing CHANGELOG Update
Every PR should update `CHANGELOG.md` under `## [Unreleased]`

---

## Disabling CI

If you don't want CI to run:

```bash
# Disable CI workflow
mv .github/workflows/ci.yml .github/workflows/ci.yml.disabled
```

To re-enable:
```bash
mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml
```

---

## For Contributors

When submitting a PR:
1. ✅ Update `CHANGELOG.md`
2. ✅ Ensure tests pass: `pytest tests/ -v`
3. ✅ Format code: `ruff format src/ cli/`
4. ✅ Check linting: `ruff check src/ cli/`

CI will verify these automatically when you open a PR.
