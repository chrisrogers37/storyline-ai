#!/bin/bash
set -e

# Storyline AI - Manual Deployment to Raspberry Pi
# Usage: ./scripts/deploy.sh [--skip-tests] [--skip-migrations]

REMOTE_HOST="crogberrypi"
REMOTE_USER="${REMOTE_USER:-crog}"
REMOTE_PATH="~/storyline-ai"
SKIP_TESTS=false
SKIP_MIGRATIONS=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--skip-tests] [--skip-migrations]"
            echo ""
            echo "Options:"
            echo "  --skip-tests       Skip running tests before deployment"
            echo "  --skip-migrations  Skip database migrations"
            exit 0
            ;;
    esac
done

echo "🚀 Storyline AI Deployment"
echo "=========================="
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo "⚠️  Warning: You have uncommitted changes"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Run tests locally
if [[ "$SKIP_TESTS" == false ]]; then
    echo ""
    echo "🧪 Running tests locally..."
    pytest tests/ -v --tb=short || {
        echo "❌ Tests failed! Aborting deployment."
        exit 1
    }
    echo "✅ Tests passed"
fi

# Push to GitHub
echo ""
echo "📤 Pushing to GitHub..."
git push origin "$CURRENT_BRANCH"

# Deploy to Pi
echo ""
echo "🔧 Deploying to Raspberry Pi..."
ssh "$REMOTE_HOST" << EOF
    set -e
    cd $REMOTE_PATH

    echo "📥 Pulling latest code..."
    git fetch origin $CURRENT_BRANCH
    git reset --hard origin/$CURRENT_BRANCH

    echo "📦 Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt -q
    pip install -e . -q

    # Run migrations
    if [[ "$SKIP_MIGRATIONS" == false ]]; then
        echo "🗃️  Running migrations..."
        for migration in scripts/migrations/*.sql; do
            if [ -f "\$migration" ]; then
                echo "  Checking: \$(basename \$migration)"
                psql -U storyline_user -d storyline_ai -f "\$migration" 2>/dev/null || true
            fi
        done
    fi

    echo "🔄 Restarting service..."
    sudo systemctl restart storyline-ai

    echo "⏳ Waiting for service to start..."
    sleep 5

    echo "🏥 Checking service health..."
    if systemctl is-active --quiet storyline-ai; then
        echo "✅ Service is running"
        storyline-cli check-health
    else
        echo "❌ Service failed to start!"
        sudo journalctl -u storyline-ai -n 20 --no-pager
        exit 1
    fi
EOF

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 View logs:"
echo "  ssh $REMOTE_HOST 'sudo journalctl -u storyline-ai -f'"
echo ""
echo "🔍 Check status:"
echo "  ssh $REMOTE_HOST 'systemctl status storyline-ai'"
