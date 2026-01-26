# Deployment Options Comparison

Three ways to deploy Storyline AI to your Raspberry Pi.

---

## ⚠️ Important: Repository Visibility

**Current Status**: Private repository ✅

**Before making repository public** (for multitenancy):
- ❌ **REMOVE** self-hosted runners - they're unsafe on public repos
- ✅ **USE** Option 1 (Manual) or Option 3 (Tailscale) for YOUR Pi
- ✅ **USE** GitHub's cloud runners (`ubuntu-latest`) for CI/CD

Self-hosted runners on public repos allow attackers to execute code on your Pi through malicious PRs.

---

## Quick Comparison

| Feature | Manual Script | Self-Hosted Runner | Tailscale VPN |
|---------|---------------|-------------------|---------------|
| **Setup Time** | 2 minutes | 15 minutes | 30 minutes |
| **Complexity** | Low | Medium | High |
| **Internet Exposure** | None | None | None (encrypted VPN) |
| **Pi Resource Usage** | None (deploys on-demand) | Medium (runs CI/CD) | None |
| **Automation** | Manual trigger | Auto on git push | Auto on git push |
| **GitHub Actions** | No | Yes (local) | Yes (cloud) |
| **Public Repo Safe?** | ✅ Yes | ❌ **NO - DANGEROUS** | ✅ Yes |
| **Best For** | Solo dev, quick iterations | Private repos only | Public or private repos |

---

## Option 1: Manual Deployment Script ⭐ Recommended for Solo Dev

**Best for**: Single developer, rapid iteration, simplicity

### How It Works

1. You run `./scripts/deploy.sh` on your Mac
2. Script pushes to GitHub
3. Script SSHs to Pi and pulls code
4. Service restarts

### Setup

Already done! Just use:

```bash
./scripts/deploy.sh
```

### Pros
- ✅ Simple - no external services
- ✅ Fast - direct SSH
- ✅ Secure - uses existing SSH config
- ✅ No Pi resource usage

### Cons
- ⚠️ Manual trigger required
- ⚠️ No automatic CI/CD on every push
- ⚠️ Only works from your Mac (or machines with SSH access)

### When to Use
- You're the only developer
- You want control over when deployments happen
- You iterate quickly and want fast deploys
- You don't need automated testing on every push

---

## Option 2: Self-Hosted GitHub Actions Runner ⭐ Recommended for Team

**Best for**: Team collaboration, automated CI/CD, full control

### How It Works

1. GitHub Actions runner runs on your Pi
2. On every push, workflows execute on Pi
3. Tests run, deployment happens automatically
4. All local - no internet exposure

### Setup

See: [github-actions-self-hosted.md](github-actions-self-hosted.md)

```bash
# On Pi
cd ~/actions-runner
./config.sh --url https://github.com/chrisrogers37/storyline-ai --token TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

### Pros
- ✅ Automated CI/CD on every push
- ✅ Full GitHub Actions features
- ✅ No internet exposure
- ✅ Team can trigger deployments via PR merge

### Cons
- ⚠️ Uses Pi resources for CI/CD jobs
- ⚠️ Pi must be always on
- ⚠️ Runner maintenance required

### When to Use
- Multiple developers on the team
- You want tests to run on every push
- You need PR checks before merge
- Pi has resources to spare (4GB+ RAM recommended)

---

## Option 3: Tailscale VPN with Cloud Runners

**Best for**: Team needing cloud CI/CD, Pi with limited resources

### How It Works

1. Tailscale creates secure VPN between GitHub and Pi
2. GitHub's cloud runners execute CI/CD
3. Runners SSH through Tailscale to deploy
4. Pi only receives deployments, doesn't run jobs

### Setup

See: [github-actions-tailscale.md](github-actions-tailscale.md)

Requires:
- Tailscale account (free for personal)
- OAuth credentials for GitHub Action
- SSH key setup

### Pros
- ✅ Automated CI/CD on every push
- ✅ No Pi resource usage for CI
- ✅ Secure VPN (no public exposure)
- ✅ GitHub's infrastructure runs tests

### Cons
- ⚠️ Depends on Tailscale service
- ⚠️ More complex setup
- ⚠️ External dependency

### When to Use
- You want automated CI/CD but Pi has limited resources
- You need advanced GitHub Actions features (matrix builds, caching)
- You already use Tailscale
- You want cloud-based test execution

---

## Recommendation by Use Case

### Solo Developer, Rapid Iteration
→ **Option 1: Manual Script**
- Fastest setup
- Most control
- Simple and reliable

### Team with Powerful Pi (4GB+ RAM)
→ **Option 2: Self-Hosted Runner**
- Full automation
- No external dependencies
- Excellent for private repos

### Team with Limited Pi Resources
→ **Option 3: Tailscale VPN**
- Cloud CI/CD benefits
- Minimal Pi resource usage
- Scales better for large test suites

---

## Migration Path

You can start simple and upgrade later:

```
Manual Script → Self-Hosted Runner → Tailscale VPN
   (Day 1)         (When team grows)    (If Pi struggles)
```

**Current Setup**: Manual script is ready to use.

**Next Step**: When you're ready for automation, add self-hosted runner (takes 15 min).

---

## Security Comparison

| Aspect | Manual | Self-Hosted | Tailscale |
|--------|--------|-------------|-----------|
| **Internet Exposure** | None | None | None (VPN encrypted) |
| **Attack Surface** | Minimal (SSH only) | Medium (runner service) | Medium (Tailscale + SSH) |
| **Secrets Management** | Local SSH config | GitHub Secrets | GitHub Secrets |
| **Audit Trail** | Git logs | GitHub Actions logs | GitHub Actions logs |

All three options are secure for a private home project.

---

## Future: Public Repo + Multitenancy

When the repository goes public and supports multitenancy:

### CI/CD Setup (Public Repo)
```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest  # ✅ Safe - isolated GitHub containers
    services:
      postgres:
        image: postgres:15
        # ... test configuration
```

### User Deployment Model

Each user deploys to their own infrastructure:

1. **User forks/clones repo**
2. **User sets up their own environment**:
   ```bash
   # On user's Pi/server
   git clone https://github.com/chrisrogers37/storyline-ai.git
   cd storyline-ai
   ./scripts/setup.sh  # Future: automated setup script
   ```
3. **User deploys using manual script**:
   ```bash
   ./scripts/deploy.sh
   ```
4. **Users manage their own Instagram credentials** (stored locally)

### Documentation for Public Users

When public, provide:
- Setup guide for new users
- Docker compose for easy deployment
- Environment variable templates
- Self-hosting documentation

**Your Pi**: You continue using manual deployment for your own Instagram accounts.

**Other users' Pis**: They deploy to their own hardware with their own credentials.

---

## Quick Start Commands

### Manual Deployment
```bash
./scripts/deploy.sh
```

### Check Self-Hosted Runner Status (Private Repo Only)
```bash
ssh crogberrypi "sudo systemctl status actions.runner.*"
```

### View GitHub Actions Logs
```bash
# Web UI
https://github.com/chrisrogers37/storyline-ai/actions

# On Pi (self-hosted - private repo only)
ssh crogberrypi "tail -f ~/actions-runner/_diag/Runner_*.log"
```
