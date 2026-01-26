#!/bin/bash
# Linting script - run before pushing to catch CI failures

set -e

echo "🔍 Running ruff check..."
python -m ruff check cli/ src/ --fix || {
    echo "❌ Ruff check failed. Please fix the errors above."
    exit 1
}

echo "✨ Running ruff format..."
python -m ruff format cli/ src/

echo "✅ All checks passed!"
