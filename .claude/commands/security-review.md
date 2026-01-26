---
description: "Review code for security vulnerabilities"
---

Perform a security review of the codebase. Check for OWASP Top 10 and project-specific risks.

## 1. Injection Vulnerabilities

**SQL Injection (should use SQLAlchemy ORM):**
```bash
grep -rE "execute\(|text\(|raw\(" src/ --include="*.py" | grep -v "alembic"
```

**Command Injection:**
```bash
grep -rE "subprocess\.|os\.system\(|os\.popen\(" src/ --include="*.py"
```

## 2. Sensitive Data Exposure

**Hardcoded secrets:**
```bash
grep -rE "(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]" src/ cli/ --include="*.py" | grep -v "\.example" | grep -v "test_"
```

**Tokens in logs:**
```bash
grep -rE "logger\.(info|debug|warning|error).*token" src/ --include="*.py"
```

**Unencrypted token storage:**
```bash
grep -rE "token_value\s*=" src/ --include="*.py" | grep -v "encrypt"
```

## 3. Authentication & Authorization

**Missing auth checks in handlers:**
```bash
grep -rE "async def (handle_|_handle_)" src/services/core/telegram_service.py | head -20
```

Review: Do all handlers verify user permissions appropriately?

## 4. Input Validation

**Unvalidated user input:**
```bash
grep -rE "update\.message\.text|query\.data" src/ --include="*.py" -A2 | grep -v "if\|validate\|check"
```

**Path traversal risks:**
```bash
grep -rE "open\(|Path\(" src/ --include="*.py" | grep -v "test_"
```

## 5. Instagram API Security

**Token refresh mechanism:**
- Verify tokens are refreshed before expiry
- Check token encryption at rest

**Rate limiting:**
- Verify rate limit checks before API calls

```bash
grep -rE "rate_limit|RateLimit" src/services/integrations/ --include="*.py"
```

## 6. Telegram Bot Security

**Webhook validation:**
```bash
grep -rE "update\.effective_user|update\.effective_chat" src/ --include="*.py"
```

**Admin command protection:**
```bash
grep -rE "@(admin_only|require_admin)" src/ --include="*.py"
```

## 7. Dependency Vulnerabilities

```bash
pip-audit 2>/dev/null || echo "Install pip-audit: pip install pip-audit"
```

## 8. Environment Security

**Check .env.example doesn't contain real values:**
```bash
grep -E "^[A-Z_]+=.+" .env.example | grep -vE "(your_|example|changeme|xxx)"
```

## Report Format

```markdown
## Security Review Results

### Critical
- [ ] Issue description with file:line

### High
- [ ] Issue description with file:line

### Medium
- [ ] Issue description with file:line

### Low
- [ ] Issue description with file:line

### Recommendations
1. Specific remediation steps
```

**IMPORTANT**: If you find actual secrets or vulnerabilities, do NOT log them. Report privately to the user.
