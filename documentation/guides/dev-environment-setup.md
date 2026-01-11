# Development Environment Setup Guide

A guide for seamless development between Mac (local) and Raspberry Pi (production).

## Current Pain Points

From today's deployment session, we encountered:

1. **Database permissions**: `storyline_user` can't create/drop databases
2. **Path differences**: Mac uses `~/Projects/storyline-ai`, Pi uses `~/storyline-ai`
3. **PostgreSQL access**: Pi requires `sudo -u postgres` for admin operations
4. **Makefile commands**: Don't work consistently across environments
5. **Manual rsync**: Have to remember the full command each time

---

## Recommended Solutions

### 1. Fix Database Permissions (One-Time Pi Setup)

Grant `storyline_user` the ability to create databases, eliminating the need for `sudo -u postgres`:

```bash
# On the Pi, run once:
sudo -u postgres psql -c "ALTER USER storyline_user CREATEDB;"
```

This allows `make create-db` and `make drop-db` to work directly.

**Alternative**: If you prefer not to grant CREATEDB, create a wrapper script (see Section 4).

---

### 2. Shell Aliases for the Pi

Add these to `~/.bashrc` on the Pi:

```bash
# Storyline AI shortcuts
alias sl='cd ~/storyline-ai && source venv/bin/activate'
alias sl-status='sudo systemctl status storyline-ai'
alias sl-restart='sudo systemctl restart storyline-ai'
alias sl-logs='sudo journalctl -u storyline-ai.service -f'
alias sl-logs-recent='sudo journalctl -u storyline-ai.service -n 100'

# Database shortcuts (if storyline_user has CREATEDB)
alias sl-db-reset='cd ~/storyline-ai && make reset-db'

# Database shortcuts (if using postgres superuser)
alias sl-db-drop='sudo -u postgres dropdb --if-exists storyline_ai'
alias sl-db-create='sudo -u postgres createdb -O storyline_user storyline_ai'
alias sl-db-init='cat ~/storyline-ai/scripts/setup_database.sql | sudo -u postgres psql -d storyline_ai && echo "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO storyline_user; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO storyline_user;" | sudo -u postgres psql -d storyline_ai'
alias sl-db-reset-full='sl-db-drop && sl-db-create && sl-db-init'

# Quick commands
alias sl-index='storyline-cli index-media ~/storyline-ai/media/stories'
alias sl-schedule='storyline-cli create-schedule --days 7'
alias sl-queue='storyline-cli list-queue'
alias sl-health='storyline-cli check-health'
alias sl-categories='storyline-cli list-categories'
```

After adding, reload:
```bash
source ~/.bashrc
```

---

### 3. Shell Aliases/Functions for Mac

Add these to `~/.zshrc` (or `~/.bashrc`) on your Mac:

```bash
# Storyline AI shortcuts
alias sl='cd ~/Projects/storyline-ai && source venv/bin/activate'

# Deployment to Pi
PI_HOST="crog@raspberrypi.local"
PI_PATH="~/storyline-ai"

# Sync media to Pi
sl-sync-media() {
    rsync -avz --progress ~/Projects/storyline-ai/media/stories/ ${PI_HOST}:${PI_PATH}/media/stories/
}

# Sync code to Pi (alternative to git pull)
sl-sync-code() {
    rsync -avz --progress --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' --exclude 'logs' --exclude '*.egg-info' ~/Projects/storyline-ai/ ${PI_HOST}:${PI_PATH}/
}

# SSH to Pi and activate environment
sl-ssh() {
    ssh -t ${PI_HOST} "cd ~/storyline-ai && source venv/bin/activate && bash"
}

# Quick deploy: push code, restart service
sl-deploy() {
    echo "Pushing to git..."
    git push origin main
    echo "Pulling on Pi and restarting..."
    ssh ${PI_HOST} "cd ~/storyline-ai && git pull && sudo systemctl restart storyline-ai"
    echo "Done! Checking logs..."
    ssh ${PI_HOST} "sudo journalctl -u storyline-ai.service -n 20"
}

# Full reset on Pi: reset db, reindex, create schedule
sl-reset-pi() {
    ssh -t ${PI_HOST} "cd ~/storyline-ai && source venv/bin/activate && sl-db-reset-full && storyline-cli index-media ~/storyline-ai/media/stories && storyline-cli create-schedule --days 7"
}
```

---

### 4. Improved Makefile (Cross-Platform)

Update the Makefile to detect environment and handle permissions:

```makefile
# Database configuration with environment detection
DB_NAME ?= storyline_ai
DB_USER ?= $(shell whoami)
DB_HOST ?= localhost

# Detect if we're on Linux (Pi) or Darwin (Mac)
UNAME := $(shell uname)

# Check if current user can create databases
CAN_CREATEDB := $(shell psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$(DB_USER)' AND rolcreatedb" 2>/dev/null || echo "0")

ifeq ($(UNAME),Linux)
    # Raspberry Pi - may need sudo for postgres
    ifeq ($(CAN_CREATEDB),1)
        DB_CMD_PREFIX :=
    else
        DB_CMD_PREFIX := sudo -u postgres
    endif
else
    # Mac - typically user has permissions
    DB_CMD_PREFIX :=
endif

.PHONY: create-db drop-db init-db reset-db

create-db:
	@echo "Creating database: $(DB_NAME)..."
	$(DB_CMD_PREFIX) createdb -O $(DB_USER) $(DB_NAME) 2>/dev/null || echo "Database may already exist"
	@echo "✓ Database ready"

drop-db:
	@echo "WARNING: This will permanently delete database: $(DB_NAME)"
	@read -p "Press Ctrl+C to cancel, or Enter to continue..." _
	@echo "Dropping database: $(DB_NAME)..."
	$(DB_CMD_PREFIX) dropdb --if-exists $(DB_NAME)
	@echo "✓ Database dropped"

init-db:
	@echo "Initializing schema..."
ifeq ($(UNAME),Linux)
	cat scripts/setup_database.sql | $(DB_CMD_PREFIX) psql -d $(DB_NAME)
	@echo "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO storyline_user; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO storyline_user;" | $(DB_CMD_PREFIX) psql -d $(DB_NAME)
else
	psql -d $(DB_NAME) -f scripts/setup_database.sql
endif
	@echo "✓ Schema initialized"

reset-db: drop-db create-db init-db
	@echo "✓ Database reset complete"
```

---

### 5. Environment File Standardization

Create a `.env.pi` template that mirrors Pi settings:

```bash
# .env.pi - Raspberry Pi production settings
DB_HOST=localhost
DB_PORT=5432
DB_NAME=storyline_ai
DB_USER=storyline_user
DB_PASSWORD=storyline2024

TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHANNEL_ID=your_channel_id
ADMIN_TELEGRAM_CHAT_ID=your_admin_chat_id

POSTS_PER_DAY=10
POSTING_HOURS_START=14
POSTING_HOURS_END=2

LOG_LEVEL=INFO
DRY_RUN_MODE=false
```

Create a `.env.dev` for Mac development with test settings.

---

### 6. Deployment Checklist Script

Create `scripts/deploy-to-pi.sh` on your Mac:

```bash
#!/bin/bash
set -e

PI_HOST="crog@raspberrypi.local"
PI_PATH="~/storyline-ai"

echo "=== Storyline AI Deployment ==="
echo ""

# Step 1: Commit check
if [[ -n $(git status -s) ]]; then
    echo "WARNING: You have uncommitted changes!"
    git status -s
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Push to git
echo "Step 1: Pushing to git..."
git push origin $(git branch --show-current)

# Step 3: Pull on Pi
echo "Step 2: Pulling on Pi..."
ssh ${PI_HOST} "cd ${PI_PATH} && git pull"

# Step 4: Check if migrations needed
echo "Step 3: Checking for schema changes..."
SCHEMA_CHANGED=$(ssh ${PI_HOST} "cd ${PI_PATH} && git diff HEAD~1 --name-only | grep -c 'setup_database.sql' || true")

if [[ "$SCHEMA_CHANGED" -gt 0 ]]; then
    echo "Schema changes detected!"
    read -p "Run database reset? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Resetting database..."
        ssh -t ${PI_HOST} "cd ${PI_PATH} && source venv/bin/activate && sl-db-reset-full"
        echo "Re-indexing media..."
        ssh -t ${PI_HOST} "cd ${PI_PATH} && source venv/bin/activate && storyline-cli index-media ~/storyline-ai/media/stories"
    fi
fi

# Step 5: Restart service
echo "Step 4: Restarting service..."
ssh ${PI_HOST} "sudo systemctl restart storyline-ai"

# Step 6: Verify
echo "Step 5: Checking service status..."
sleep 2
ssh ${PI_HOST} "sudo systemctl status storyline-ai --no-pager | head -20"

echo ""
echo "=== Deployment Complete ==="
echo "Run 'ssh ${PI_HOST}' and 'sl-logs' to monitor"
```

Make it executable:
```bash
chmod +x scripts/deploy-to-pi.sh
```

---

### 7. Quick Reference Card

Print this and keep it handy:

```
=== MAC COMMANDS ===
sl                  - cd to project, activate venv
sl-sync-media       - rsync media to Pi
sl-deploy           - git push, pull on Pi, restart
sl-ssh              - SSH to Pi with venv activated

=== PI COMMANDS ===
sl                  - cd to project, activate venv
sl-status           - systemctl status
sl-restart          - systemctl restart
sl-logs             - follow service logs
sl-db-reset-full    - drop, create, init database
sl-index            - index media
sl-schedule         - create 7-day schedule
sl-queue            - view queue
sl-health           - health check

=== FULL RESET WORKFLOW ===
Mac:  git push origin main
Pi:   sl-db-reset-full
Pi:   sl-index
Pi:   sl-schedule
Pi:   sl-restart
```

---

## Implementation Checklist

- [ ] **Pi: Grant CREATEDB to storyline_user** (optional but recommended)
  ```bash
  sudo -u postgres psql -c "ALTER USER storyline_user CREATEDB;"
  ```

- [ ] **Pi: Add aliases to ~/.bashrc**
  - Copy aliases from Section 2
  - Run `source ~/.bashrc`

- [ ] **Mac: Add aliases to ~/.zshrc**
  - Copy aliases/functions from Section 3
  - Update `PI_HOST` if your Pi has a different hostname
  - Run `source ~/.zshrc`

- [ ] **Mac: Create deploy script**
  - Copy script from Section 6 to `scripts/deploy-to-pi.sh`
  - Run `chmod +x scripts/deploy-to-pi.sh`

- [ ] **Both: Update Makefile** (optional)
  - Replace database targets with cross-platform version

- [ ] **Test the workflow**
  - Mac: `sl-ssh` to connect to Pi
  - Pi: `sl-logs` to check service
  - Mac: `sl-sync-media` to sync files
  - Mac: `sl-deploy` for full deployment

---

## Future Improvements

1. **Docker**: Containerize the app for identical environments
2. **Ansible**: Automate Pi provisioning and deployment
3. **GitHub Actions**: Auto-deploy on push to main
4. **Tailscale**: VPN for accessing Pi from anywhere

---

*Last updated: 2026-01-10*
