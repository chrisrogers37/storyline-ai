# GitHub Actions with Tailscale VPN

## Overview

Use Tailscale to create a secure mesh VPN so GitHub's cloud runners can SSH to your Raspberry Pi without exposing it to the public internet.

---

## Setup Tailscale

### 1. Install on Raspberry Pi

```bash
ssh crogberrypi

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Start and authenticate
sudo tailscale up

# Note the Tailscale IP (usually 100.x.x.x)
tailscale ip -4
```

### 2. Enable SSH on Tailscale

```bash
# Allow SSH through Tailscale
sudo tailscale up --ssh
```

### 3. Create Tailscale Auth Key

1. Go to: https://login.tailscale.com/admin/settings/keys
2. Click **"Generate auth key"**
3. Options:
   - ✅ Reusable
   - ✅ Ephemeral (for CI/CD runners)
   - Expiration: 90 days (or longer)
4. Copy the key (starts with `tskey-auth-...`)

---

## Configure GitHub Secrets

Go to: `https://github.com/chrisrogers37/storyline-ai/settings/secrets/actions`

Add these secrets:

| Secret | Value | Example |
|--------|-------|---------|
| `TAILSCALE_AUTH_KEY` | Auth key from step 3 | `tskey-auth-xxxxx` |
| `PI_TAILSCALE_IP` | Pi's Tailscale IP | `100.64.1.2` |
| `PI_USER` | SSH username | `pi` or your username |
| `PI_SSH_KEY` | Private SSH key for Pi | (generate dedicated key) |

---

## Generate Dedicated SSH Key for CI/CD

```bash
# On your Mac
cd ~/.ssh
ssh-keygen -t ed25519 -C "github-actions-storyline" -f github_actions_pi

# Copy public key to Pi
ssh-copy-id -i github_actions_pi.pub crogberrypi

# Test it works
ssh -i github_actions_pi pi@crogberrypi "echo 'SSH works'"

# Copy private key content for GitHub secret
cat github_actions_pi
# Copy the entire output (including BEGIN/END lines) as PI_SSH_KEY secret
```

---

## Update Deployment Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to Pi via Tailscale

on:
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Connect to Tailscale
        uses: tailscale/github-action@v2
        with:
          oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
          oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
          tags: tag:ci

      - name: Set up SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.PI_SSH_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H ${{ secrets.PI_TAILSCALE_IP }} >> ~/.ssh/known_hosts

      - name: Deploy to Pi
        run: |
          ssh -i ~/.ssh/id_ed25519 ${{ secrets.PI_USER }}@${{ secrets.PI_TAILSCALE_IP }} << 'EOF'
            cd ~/storyline-ai
            git pull origin main
            source venv/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart storyline-ai
            storyline-cli check-health
          EOF
```

**Note**: You'll need to create OAuth credentials in Tailscale for the GitHub Action. See: https://tailscale.com/kb/1215/oauth-clients

---

## Advantages

✅ **Secure** - No public exposure, encrypted VPN
✅ **Cloud runner** - Pi doesn't run CI/CD jobs (saves resources)
✅ **Easy setup** - Tailscale is well-documented
✅ **Free for personal use** - Up to 100 devices

## Disadvantages

⚠️ **Dependency on Tailscale** - Service must be running on Pi
⚠️ **Ephemeral IPs** - Tailscale IP can change (though rare)
⚠️ **External service** - Relies on Tailscale infrastructure

---

## Troubleshooting

### Can't SSH from GitHub Actions

```bash
# On Pi, check Tailscale status
sudo tailscale status

# Verify SSH is enabled
sudo tailscale up --ssh

# Check firewall (shouldn't be needed with Tailscale)
sudo ufw status
```

### Tailscale Connection Lost

```bash
# Restart Tailscale service
sudo systemctl restart tailscaled

# Re-authenticate if needed
sudo tailscale up
```

---

## Cost

- **Free** for personal use (up to 3 users, 100 devices)
- **Paid plans** if you need more devices or team features

---

## Security Best Practices

1. Use ephemeral keys for GitHub Actions runners
2. Rotate SSH keys periodically
3. Use dedicated SSH key (not your personal key)
4. Enable MagicDNS for stable hostnames instead of IPs
5. Use ACLs in Tailscale to restrict access to specific devices
