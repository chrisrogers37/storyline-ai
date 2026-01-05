# Project Updates

This folder contains dated documentation for bug fixes, patches, hotfixes, and other significant project updates.

## Purpose

- Track bug fixes and their resolutions
- Document patches and hotfixes
- Provide historical context for changes
- Maintain audit trail of production issues

## Naming Convention

All files in this folder **must** use the ISO date format:

```
YYYY-MM-DD-description.md
```

### Examples

✅ **Correct**:
- `2026-01-04-bugfixes.md`
- `2026-02-15-security-patch.md`
- `2026-03-20-hotfix-telegram.md`
- `2026-04-10-performance-improvements.md`

❌ **Incorrect**:
- `bugfixes.md` (missing date)
- `Jan-04-2026-bugfixes.md` (wrong format)
- `2026-1-4-bugfixes.md` (missing leading zeros)
- `bugfix-jan-4.md` (text month, missing year)

## File Template

When creating a new update document, use this structure:

```markdown
# [Type] - YYYY-MM-DD

Brief description of the update.

---

## Summary

High-level overview of what was changed and why.

## Issues Fixed / Changes Made

### 1. Issue Title

**Severity**: Critical/High/Medium/Low
**Location**: `file/path.py:line`
**Identified By**: Code review / Deployment / Production / User report

**Issue**:
Description of the problem.

**Impact**:
- What broke or didn't work
- Who was affected

**Fix**:
```python
# Before
problematic_code()

# After
fixed_code()
```

**Verification**:
How the fix was tested and verified.

---

## Files Changed

1. `path/to/file1.py` - Description
2. `path/to/file2.py` - Description

## Deployment Status

Status of deployment and verification.

## Related Links

- PR: #123
- Issue: #456
- Discussion: link
```

## Index

### 2026

- **[2026-01-04](2026-01-04-bugfixes.md)** - Critical bug fixes (4 issues)
  - Service run metadata column mismatch
  - Scheduler date mutation bug
  - Health check SQLAlchemy compatibility
  - Missing 30-day lock creation

---

*Last updated: 2026-01-04*
