---
description: "Commit, push, and open a PR"
---

Here is the current git status:
```
${{ git status --short }}
```

Here is the current branch:
```
${{ git branch --show-current }}
```

Here are the changes:
```
${{ git diff --stat }}
```

Recent commit messages for style reference:
```
${{ git log --oneline -5 }}
```

Follow these steps in order:

1. Review the changes above
2. Run the verification loop before committing:
   - `pytest tests/ -v --tb=short`
   - `ruff check src/`
3. Stage the appropriate files with `git add`
4. Create a commit with a clear, descriptive message following conventional commits format
5. Push to the remote branch (create remote branch if needed with `-u origin <branch>`)
6. Create a Pull Request using `gh pr create` with:
   - A clear title summarizing the changes
   - A description with:
     - Summary of what changed and why
     - Any testing done
     - Breaking changes or migration notes if applicable
     - CHANGELOG.md updates included

If there are any issues at any step, stop and report them.

**REMINDER**: Ensure CHANGELOG.md is updated before creating PR.
