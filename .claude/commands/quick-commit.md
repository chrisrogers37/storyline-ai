---
description: "Stage all changes and commit with a descriptive message"
---

Here is the current git status:
```
${{ git status --short }}
```

Here is the diff of changes:
```
${{ git diff --stat }}
```

Recent commit messages for style reference:
```
${{ git log --oneline -5 }}
```

Based on the above:
1. Stage all changes with `git add -A`
2. Create a commit with a clear message that:
   - Starts with a type prefix (feat:, fix:, refactor:, docs:, test:, chore:)
   - Briefly describes what changed
   - Uses imperative mood ("Add feature" not "Added feature")

Example: `feat: add multi-account Instagram switching`

**IMPORTANT**: If significant changes were made, remind about CHANGELOG.md update.
