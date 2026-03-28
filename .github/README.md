# GitHub Workflows

This directory contains GitHub Actions workflows for CI.

---

## Current Setup

### Continuous Integration (Automated)

**File**: `ci.yml`

Runs automatically on every push and pull request:
- **Lint** - Code style checks with ruff
- **Test** - Unit and integration tests with pytest
- **Security** - Vulnerability scanning with pip-audit and bandit
- **Changelog** - Verify CHANGELOG.md is updated

All jobs run on **GitHub's cloud runners** (`ubuntu-latest`) — safe for public repositories.

### Continuous Deployment (Railway Auto-Deploy)

Railway automatically deploys when changes are pushed to `main`:
1. Push to `main` triggers Railway build
2. Railway installs dependencies and builds both services
3. Health checks verify the deployment

No GitHub Actions deploy workflow is needed — Railway's GitHub integration handles CD.

See: [documentation/guides/ci-cd-pipeline.md](../documentation/guides/ci-cd-pipeline.md)

---

## CI Failures

If CI is failing, common issues:

### Lint Errors
```bash
# Fix automatically
ruff format src/ tests/ cli/

# Check for issues
ruff check src/ tests/ cli/
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

## For Contributors

When submitting a PR:
1. Update `CHANGELOG.md`
2. Ensure tests pass: `pytest tests/ -v`
3. Format code: `ruff format src/ tests/ cli/`
4. Check linting: `ruff check src/ tests/ cli/`

CI will verify these automatically when you open a PR.
