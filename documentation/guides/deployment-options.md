# Deployment Options

**Repository Status**: PUBLIC

---

## Current Setup: Railway Auto-Deploy

### How It Works

Railway automatically deploys when changes are pushed to `main`:

1. Push to `main` (or merge a PR)
2. Railway detects the change via GitHub integration
3. Railway builds both services (worker + web)
4. Railway restarts services with new code
5. Health checks verify the deployment

### Pros
- **Automated** -- deploy on every push to main
- **Safe for public repos** -- no self-hosted runners
- **Simple** -- no SSH keys, VPNs, or tunneling
- **Reliable** -- Railway manages restarts and health checks
- **Fast** -- builds typically complete in 1-2 minutes

### Cons
- Monthly cost (~$5-10/month for Railway)
- Dependent on Railway infrastructure

---

## CI/CD Pipeline

### Continuous Integration (Automated)

GitHub Actions runs automatically on every push/PR:
- **Linting** (ruff) -- code style checks
- **Tests** (pytest) -- unit and integration tests
- **Security** (pip-audit, bandit) -- vulnerability scanning

All CI runs on **GitHub cloud runners** (`ubuntu-latest`) -- safe for public repos.

### Continuous Deployment (Automated via Railway)

Railway deploys automatically when CI passes and changes land on `main`. No manual deployment step required.

### Manual Deployment (if needed)

```bash
# Force a redeploy via Railway CLI
railway up --service worker
railway up --service web

# Or trigger via Railway dashboard
```

---

## Why Not Self-Hosted Runners?

**Self-hosted runners on public repos are DANGEROUS**:
- Attackers can submit PRs with malicious code
- Workflows execute on YOUR infrastructure
- Your secrets, network, and data are exposed

See: [GitHub's security warning](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security)

All CI runs on **GitHub cloud runners** (`ubuntu-latest`), which are safe for public repositories.

---

## Multitenancy Model

When others use this project:

1. **Users fork/clone the repository**
2. **Users create their own Railway project**
3. **Users set up their own Neon database**
4. **Users configure their own environment variables** in Railway
5. **Users deploy to their own Railway services**

**Your infrastructure is never accessed by other users.** Everyone runs their own instance.

---

## Quick Reference

| Task | Command |
|------|---------|
| **Check deploy status** | Railway dashboard or `railway logs` |
| **View worker logs** | `railway logs --service worker` |
| **View web logs** | `railway logs --service web` |
| **Force redeploy** | `railway up` or push to `main` |
| **Run health check** | `railway shell --service worker -c "storydump-cli check-health"` |
| **Run tests locally** | `pytest tests/ -v` |
| **View CI status** | GitHub Actions tab in repo |

---

## Summary

- **CI runs automatically** on GitHub cloud runners (`ubuntu-latest`) -- safe for public repos
- **CD runs automatically** via Railway GitHub integration on push to `main`
- **No manual deployment required** -- merge to main and Railway handles the rest
- **No self-hosted runners** -- all CI/CD uses managed cloud infrastructure
