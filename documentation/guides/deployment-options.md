# Deployment for Public Repository

**Repository Status**: PUBLIC ✅

Since this is a public repository, deployment is done **manually** for security.

---

## ⚠️ Why Not Automated Deployment?

**Self-hosted runners on public repos are DANGEROUS**:
- Attackers can submit PRs with malicious code
- Workflows execute on YOUR Pi
- Your secrets, network, and data are exposed

See: [GitHub's security warning](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security)

---

## Current Setup: Manual Deployment ✅

### How It Works

Run this command from your Mac:

```bash
./scripts/deploy.sh
```

The script will:
1. ✅ Run tests locally
2. ✅ Push to GitHub
3. ✅ SSH to your Pi (using `crogberrypi` alias)
4. ✅ Pull latest code
5. ✅ Install dependencies
6. ✅ Run database migrations
7. ✅ Restart service
8. ✅ Verify deployment

### Script Options

```bash
# Normal deployment (with tests)
./scripts/deploy.sh

# Skip tests (faster, but risky)
./scripts/deploy.sh --skip-tests

# Skip database migrations
./scripts/deploy.sh --skip-migrations
```

### Pros
- ✅ **Safe for public repos** - uses your SSH access only
- ✅ **Simple** - no external services
- ✅ **Fast** - direct SSH connection
- ✅ **Secure** - no secrets stored in GitHub
- ✅ **You control timing** - deploy when ready

### Cons
- ⚠️ Manual trigger required
- ⚠️ Only works from machines with SSH access to Pi

---

## CI/CD Pipeline

### Continuous Integration (Automated)

GitHub Actions runs automatically on every push/PR:
- ✅ **Linting** (ruff) - code style checks
- ✅ **Tests** (pytest) - unit and integration tests
- ✅ **Security** (pip-audit, bandit) - vulnerability scanning

All CI runs on **GitHub's cloud runners** (`ubuntu-latest`) - safe for public repos.

### Continuous Deployment (Manual)

**Deployment is NOT automated** for security. You must manually run:

```bash
./scripts/deploy.sh
```

This keeps your Pi secure and your credentials private.

---

## Alternative: Tailscale VPN (Advanced)

If you need automated deployment, use Tailscale VPN.

### How It Works

1. Tailscale creates secure VPN between GitHub and your Pi
2. GitHub's cloud runners execute CI/CD
3. Runners SSH through Tailscale to deploy
4. Pi never exposed to public internet

### Setup

See: [github-actions-tailscale.md](github-actions-tailscale.md)

Requires:
- Tailscale account (free for personal use)
- OAuth credentials for GitHub Action
- Dedicated SSH key for CI/CD
- GitHub secrets configuration

### Pros
- ✅ Safe for public repos
- ✅ Automated deployment on every push
- ✅ No Pi resource usage for CI

### Cons
- ⚠️ Complex setup (30+ minutes)
- ⚠️ Depends on external service (Tailscale)

---

## Multitenancy Model

When others use this project:

1. **Users fork/clone the repository**
2. **Users set up their own Pi/server**
3. **Users configure their own `.env`** with their credentials
4. **Users deploy to their own infrastructure** using `./scripts/deploy.sh`

**Your Pi is never accessed by other users.** Everyone runs their own instance.

---

## Quick Reference

| Task | Command |
|------|---------|
| **Deploy to your Pi** | `./scripts/deploy.sh` |
| **View deployment logs** | `ssh crogberrypi "sudo journalctl -u storyline-ai -f"` |
| **Check service status** | `ssh crogberrypi "systemctl status storyline-ai"` |
| **Run tests locally** | `pytest tests/ -v` |
| **View CI status** | GitHub Actions tab in repo |

---

## Summary

✅ **Manual deployment** is the right choice for public repos

✅ **CI runs automatically** on GitHub's cloud runners (safe)

✅ **You deploy manually** when ready using `./scripts/deploy.sh`

✅ **Your Pi is secure** - no exposure to malicious PRs
