---
description: "Review code for architecture violations and best practices"
---

Review the codebase for common issues. Check the following:

## 1. Layer Violation Check

Search for imports that violate the 3-layer architecture:

**Services should NOT directly import models (except for type hints):**
```bash
grep -r "from src.models" src/services/ --include="*.py" | grep -v "# type:" | grep -v "TYPE_CHECKING"
```

**CLI should NOT import repositories directly:**
```bash
grep -r "from src.repositories" cli/ --include="*.py"
```

**Repositories should NOT contain business logic keywords:**
```bash
grep -rE "(if.*then|validate|calculate|process)" src/repositories/ --include="*.py"
```

## 2. Security Check

**Hardcoded secrets:**
```bash
grep -rE "(password|secret|token|key)\s*=\s*['\"]" src/ --include="*.py" | grep -v ".example" | grep -v "test"
```

**Raw SQL in services:**
```bash
grep -rE "execute\(|raw\(|text\(" src/services/ --include="*.py"
```

## 3. Error Handling Check

**Bare except clauses:**
```bash
grep -rE "except:" src/ --include="*.py"
```

**Missing error handling in API calls:**
```bash
grep -rE "requests\.(get|post|put|delete)" src/ --include="*.py" -A2 | grep -v "try:"
```

## 4. Test Coverage Check

```bash
pytest --cov=src --cov-report=term-missing --cov-fail-under=70
```

## 5. Report Format

Summarize findings:
- **Critical**: Layer violations, security issues
- **Warning**: Missing error handling, bare excepts
- **Info**: Style improvements, documentation gaps

Provide specific file:line references for each issue found.
