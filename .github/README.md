# GitHub Workflows

This directory contains optional GitHub Actions workflows for CI/CD.

## Current Setup: Manual Deployment (Option 1)

The simplest deployment method is already configured:

```bash
./scripts/deploy.sh
```

This script:
- Runs tests locally
- Pushes to GitHub
- SSHs to your Pi and deploys
- Restarts the service

**No GitHub Actions setup required.**

---

## Optional: Automated CI/CD

If you want automated testing and deployment on every push, see:

**[documentation/guides/deployment-options.md](../documentation/guides/deployment-options.md)**

### Available Workflows

| Workflow | Purpose | Status | Setup Required |
|----------|---------|--------|----------------|
| **ci.yml** | Lint, test, security scan | ⚠️ Will fail without setup | Setup Python service on GitHub runners OR use self-hosted runner |
| **deploy.yml** | Deploy to Pi via Tailscale | 🔒 Disabled by default | Requires Tailscale + secrets |

---

## Quick Setup Options

### Option 2: Self-Hosted Runner (Recommended)

Run GitHub Actions on your Pi:

```bash
# On Pi
mkdir -p ~/actions-runner && cd ~/actions-runner
# Follow instructions from: https://github.com/chrisrogers37/storyline-ai/settings/actions/runners
```

See: [documentation/guides/github-actions-self-hosted.md](../documentation/guides/github-actions-self-hosted.md)

### Option 3: Tailscale VPN

Use GitHub's cloud runners with secure VPN:

See: [documentation/guides/github-actions-tailscale.md](../documentation/guides/github-actions-tailscale.md)

---

## Disabling Workflows

If you prefer manual deployment only:

```bash
# Disable CI/CD (workflows won't run)
rm -rf .github/workflows/

# Or just disable specific workflows
mv .github/workflows/ci.yml .github/workflows/ci.yml.disabled
```

---

## Current Recommendation

For a solo developer project: **Use manual deployment (Option 1)**
- Already set up
- Fast and simple
- No additional configuration needed

Upgrade to automated CI/CD when:
- You add team members
- You want tests to run on every push
- You need deployment automation
