---
description: "Review uncommitted changes and suggest improvements"
---

Here is the current git status:
```
${{ git status --short }}
```

Here are the changes:
```
${{ git diff }}
```

For each modified file, analyze:
1. Is the change correct and complete?
2. Are there any potential bugs?
3. Does it follow project conventions?
   - Type hints on function signatures
   - Docstrings on public methods
   - Proper error handling with specific exceptions
4. Are there any security concerns?
   - No raw SQL (use repositories)
   - No hardcoded secrets
   - Proper input validation
5. Is error handling adequate?
6. For Telegram handlers: Is user input properly validated?

Run the verification loop:
- `pytest tests/ -v --tb=short` for quick test validation
- `ruff check src/` for linting

Provide a summary with:
- What looks good
- Any concerns or suggestions
- Recommended next steps (test more, commit, or make changes)
- CHANGELOG.md reminder if significant changes
