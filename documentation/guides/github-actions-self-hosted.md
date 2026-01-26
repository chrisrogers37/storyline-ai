# Self-Hosted GitHub Actions Runner Setup

## Overview

Run GitHub Actions on your Raspberry Pi so CI/CD workflows can execute locally without exposing your Pi to the internet.

---

## Installation on Raspberry Pi

### 1. Go to GitHub Repository Settings

1. Navigate to: `https://github.com/chrisrogers37/storyline-ai/settings/actions/runners`
2. Click **"New self-hosted runner"**
3. Select **"Linux"** and **"ARM64"** (for Pi 4/5) or **"ARM"** (for older Pi)
4. Follow the commands shown (customized for your repo)

### 2. Install Runner on Pi

```bash
# SSH to Pi
ssh crogberrypi

# Create runner directory
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the runner (ARM64 for Pi 4/5)
curl -o actions-runner-linux-arm64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz

# Extract
tar xzf ./actions-runner-linux-arm64-2.311.0.tar.gz

# Configure (use token from GitHub UI)
./config.sh --url https://github.com/chrisrogers37/storyline-ai --token YOUR_TOKEN

# Test run (foreground)
./run.sh
```

### 3. Install as System Service

```bash
# Install service (still on Pi)
sudo ./svc.sh install

# Start service
sudo ./svc.sh start

# Check status
sudo ./svc.sh status

# Enable auto-start on boot
sudo systemctl enable actions.runner.chrisrogers37-storyline-ai.*
```

### 4. Verify Runner is Online

Go to: `https://github.com/chrisrogers37/storyline-ai/settings/actions/runners`

You should see your runner with a green "Idle" status.

---

## Update Workflows to Use Self-Hosted Runner

Change `runs-on: ubuntu-latest` to `runs-on: self-hosted`:

```yaml
# .github/workflows/ci.yml
jobs:
  lint:
    runs-on: self-hosted  # Changed from ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... rest of workflow
```

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: self-hosted  # Changed from ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # No SSH needed - runner is already on Pi!
      - name: Deploy
        run: |
          cd ~/storyline-ai
          git pull origin main
          source venv/bin/activate
          pip install -r requirements.txt
          sudo systemctl restart storyline-ai
```

---

## Advantages

✅ **No internet exposure** - Pi stays on local network
✅ **No SSH key management** - Runner already has local access
✅ **Fast** - No network latency for deployments
✅ **Secure** - All CI/CD runs locally

## Disadvantages

⚠️ **Pi must be always on** - Runner needs to be running for CI/CD
⚠️ **Resource usage** - CI/CD jobs consume Pi CPU/RAM
⚠️ **Maintenance** - Need to update runner occasionally

---

## Maintenance

### Update Runner

```bash
ssh crogberrypi
cd ~/actions-runner
sudo ./svc.sh stop
./config.sh remove  # Remove old config
# Re-run installation steps from GitHub UI
sudo ./svc.sh install
sudo ./svc.sh start
```

### View Logs

```bash
# Service logs
sudo journalctl -u actions.runner.* -f

# Runner logs
cd ~/actions-runner/_diag
tail -f Runner_*.log
```

### Uninstall

```bash
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove
```

---

## Security Notes

⚠️ **CRITICAL: DO NOT USE SELF-HOSTED RUNNERS ON PUBLIC REPOSITORIES**

### Why This Matters

If your repository is public:
- ✅ GitHub's cloud runners (`ubuntu-latest`) are safe - they run in isolated containers
- ❌ Self-hosted runners are **DANGEROUS** - attackers can run code on your Pi

### The Attack Vector

1. Attacker forks your public repo
2. Attacker creates a PR with malicious workflow code
3. Workflow runs on YOUR self-hosted runner (your Pi)
4. Attacker now has code execution on your Pi and can:
   - Read your secrets (Instagram tokens, database passwords)
   - Access your local network
   - Mine cryptocurrency
   - Steal data from your Pi
   - Use your Pi as a botnet node

GitHub explicitly warns against this: [Self-hosted runner security](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security)

### Current Status

**Repository**: Private ✅
**Self-hosted runner**: Safe to use ✅

### Before Making Repository Public

**YOU MUST**:
1. Remove self-hosted runner: `./svc.sh stop && ./svc.sh uninstall`
2. Change workflows to `runs-on: ubuntu-latest` (GitHub's cloud runners)
3. For your own Pi deployment, use:
   - **Option 1**: Manual deployment (`./scripts/deploy.sh`)
   - **Option 3**: Tailscale VPN (secure, no runner on Pi)

### Protected Branches (NOT A SOLUTION)

Some developers think "I'll only run workflows on main branch." **This doesn't work:**
- PRs still trigger workflows before merge
- Branch protection doesn't prevent workflow execution
- You'd need to manually approve EVERY PR before CI runs

### Recommended Setup for Public Repos

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest  # ✅ Safe for public repos
    services:
      postgres:
        image: postgres:15
        # ... test database config

  # Remove any jobs with runs-on: self-hosted
```

**For deployment to your own Pi**: Use manual script or Tailscale VPN, NOT self-hosted runner.

### Summary

| Repository Visibility | Self-Hosted Runner | Recommendation |
|-----------------------|-------------------|----------------|
| **Private** | ✅ Safe | Use self-hosted for convenience |
| **Public** | ❌ DANGEROUS | Use cloud runners + manual deploy |
| **Public (future multitenancy)** | ❌ NEVER | Cloud CI + users deploy to their own infra |
