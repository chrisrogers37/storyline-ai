# GitHub Actions CI/CD

## Overview

Storydump uses GitHub Actions for continuous integration and Railway for continuous deployment. Since the project is hosted on a public repository, all CI runs on GitHub's cloud runners (`ubuntu-latest`).

---

## CI Pipeline (Automated)

GitHub Actions runs automatically on every push and pull request:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .

      - name: Lint
        run: |
          ruff check src/ tests/ cli/
          ruff format --check src/ tests/ cli/

      - name: Test
        run: pytest

      - name: Security scan
        run: |
          pip-audit
          bandit -r src/ -c pyproject.toml
```

### What CI Checks

| Check | Tool | Purpose |
|-------|------|---------|
| Linting | `ruff check` | Code style and errors |
| Formatting | `ruff format --check` | Consistent code formatting |
| Tests | `pytest` | Unit and integration tests |
| Security | `pip-audit`, `bandit` | Vulnerability scanning |
| Changelog | Custom check | CHANGELOG.md updated in PRs |

---

## CD Pipeline (Railway Auto-Deploy)

Railway automatically deploys when changes are pushed to `main`:

1. Push to `main` triggers Railway build
2. Railway installs dependencies (`pip install -r requirements.txt && pip install -e . && mkdir -p /tmp/media`)
3. Railway restarts both services (worker + web)
4. Health checks verify the deployment

### Railway Services

| Service | Start Command | Purpose |
|---------|--------------|---------|
| Worker | `python -m src.main` | Telegram bot + scheduler |
| Web | `uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}` | OAuth callbacks + API |

### Monitoring Deploys

```bash
# Check deployment status
railway logs --service worker
railway logs --service web

# Verify health after deploy
railway shell --service worker -c "storydump-cli check-health"
```

---

## Security for Public Repos

Since this is a public repository:

- All CI runs on **GitHub cloud runners** (`ubuntu-latest`) -- safe for public repos
- No self-hosted runners are used (avoids exposing infrastructure to malicious PRs)
- All secrets are stored in **Railway environment variables** (never in code)
- Deployment is triggered by Railway's GitHub integration (not by CI)

See: [GitHub's security warning about self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security)

---

## Environment Setup

### GitHub Secrets (for CI only)

Go to: `https://github.com/chrisrogers37/storydump/settings/secrets/actions`

| Secret | Purpose | Notes |
|--------|---------|-------|
| None required | CI uses no secrets | Tests use mocked dependencies |

### Railway Secrets (for CD)

All production secrets are configured in the Railway dashboard:
- `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `ENCRYPTION_KEY`, etc.
- See [cloud-deployment.md](cloud-deployment.md) for full env var reference

---

## Advantages

- **Secure** -- No infrastructure exposed to public PRs
- **Cloud runners** -- No local resources used for CI
- **Auto-deploy** -- Railway deploys on push to main
- **Simple** -- No VPN, SSH keys, or tunneling required

---

## Troubleshooting

### CI Failing

```bash
# Run checks locally before pushing
source venv/bin/activate
ruff check src/ tests/ cli/
ruff format --check src/ tests/ cli/
pytest
```

### Railway Deploy Not Triggering

- Verify Railway GitHub integration is connected
- Check Railway dashboard for build errors
- Ensure the branch matches Railway's configured branch

### Service Not Starting After Deploy

```bash
# Check Railway logs
railway logs --service worker

# Common issues:
# - Missing env var -> Add in Railway dashboard
# - Build failed -> Check build logs
# - Database unreachable -> Verify DATABASE_URL
```

---

## Cost

- **GitHub Actions**: Free for public repos (unlimited minutes)
- **Railway**: ~$5-10/month (worker + web services)
- **Neon**: Free tier (0.5 GB, 190 compute-hours)
