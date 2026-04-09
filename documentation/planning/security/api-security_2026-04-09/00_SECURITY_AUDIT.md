# Security Audit: Storyline AI

| Field | Value |
|-------|-------|
| **Audit Date** | 2026-04-09 |
| **Scope** | Full codebase security audit (Python backend, FastAPI API, Telegram Mini App, Next.js landing site) |
| **Auditor** | Claude Code (automated static analysis + manual review) |
| **Secret Detection** | **CLEAN** -- no hardcoded secrets found in source code, tracked files, or git history |
| **Total Findings** | 15 (4 HIGH, 5 MEDIUM, 5 LOW, 1 INFO) |
| **Remediation PRs** | 5 planned |

---

## Table of Contents

1. [Audit Scope](#1-audit-scope)
2. [Secret Detection Results](#2-secret-detection-results)
3. [Findings Table](#3-findings-table)
4. [Detailed Findings](#4-detailed-findings)
5. [Remediation Plan](#5-remediation-plan)
6. [PR Grouping Rationale](#6-pr-grouping-rationale)
7. [Dependency Matrix](#7-dependency-matrix)
8. [Findings Not Requiring PRs](#8-findings-not-requiring-prs)
9. [Positive Findings](#9-positive-findings)

---

## 1. Audit Scope

### Areas Covered

| Area | Description | Research File |
|------|-------------|---------------|
| **Auth, Transport & Endpoints** | Telegram initData validation, OAuth flows, tenant isolation, security headers, rate limiting | `auth-transport-endpoints.md` |
| **OWASP Top 10** | SQL injection, XSS, IDOR, command injection, deserialization, path traversal, CSRF | `owasp.md` |
| **Dependencies** | Python (pip) and npm vulnerability scanning, version pinning, lock file hygiene | `dependencies.md` |
| **Secrets & Environment** | Hardcoded secrets, .env hygiene, .gitignore coverage, test fixtures | `secrets-env.md` |

### Components in Scope

- **Python backend**: `src/` -- FastAPI API, services, repositories, models, Telegram bot
- **CLI**: `cli/` -- storyline-cli commands
- **FastAPI API**: `src/api/` -- REST endpoints, OAuth routes, onboarding Mini App
- **Telegram Mini App**: `src/api/static/onboarding/` -- client-side JavaScript
- **Next.js landing site**: `landing/` -- public website with drizzle-orm + Neon PostgreSQL
- **Infrastructure**: Railway deployment, Neon PostgreSQL, environment configuration

---

## 2. Secret Detection Results

**Result: CLEAN**

| Check | Status |
|-------|--------|
| Hardcoded secrets in source code (`src/`, `cli/`) | PASS -- all secrets loaded via Pydantic Settings |
| Test files use mock values | PASS -- fake tokens, masked placeholders |
| Documentation uses placeholder values | PASS -- `user:pass@ep-xxx.neon.tech` patterns |
| `.gitignore` covers all env files | PASS -- `.env`, `.env.test`, `.env.local` all ignored |
| `.env.example` contains only placeholders | PASS -- blank or `your_*_here` values |
| No `os.environ` / `os.getenv` in application code | PASS -- exclusively Pydantic `BaseSettings` |
| Git history clean | PASS -- no secrets ever committed |

---

## 3. Findings Table

| # | Finding | Severity | Category | Exploitable | Remediation PR |
|---|---------|----------|----------|-------------|----------------|
| 1 | Tenant isolation bypass via initData without chat field | **HIGH** | Authentication | Yes -- any valid Telegram user in private chat | PR 01 |
| 2 | Unauthenticated OAuth start endpoints allow account hijacking | **HIGH** | Authorization | Yes -- no auth required | PR 01 |
| 3 | `cryptography` 46.0.3 -- 2 CVEs (key leakage + DNS bypass) | **HIGH** | Dependencies | Yes -- production token encryption | PR 02 |
| 4 | `drizzle-orm` SQL injection in landing site | **HIGH** | Dependencies | Yes -- if user input reaches identifiers | PR 04 |
| 5 | Cross-tenant account operations (remove, list) -- IDOR | **MEDIUM** | Authorization | Yes -- requires valid auth + target UUID | PR 01 |
| 6 | `starlette` 0.52.1 CORS misconfiguration CVE | **MEDIUM** | Dependencies | Possible -- framework may override app config | PR 02 |
| 7 | `requests` 2.32.5 file replacement CVE | **MEDIUM** | Dependencies | Low -- utility function unlikely called directly | PR 02 |
| 8 | FastAPI docs/redoc/openapi exposed in production | **MEDIUM** | Exposed Endpoints | Yes -- full API schema publicly accessible | PR 03 |
| 9 | Missing security headers (HSTS, X-Frame-Options, etc.) | **MEDIUM** | Transport Security | Yes -- clickjacking, MIME confusion | PR 03 |
| 10 | No rate limiting on any API endpoint | **LOW** | Availability | Yes -- requires valid auth for most endpoints | PR 03 |
| 11 | `innerHTML` without escaping on controlled data | **LOW** | XSS | No -- all dynamic values currently escaped at source | None (informational) |
| 12 | Next.js 16.1.6 -- 5 moderate vulnerabilities | **LOW** | Dependencies | Low -- CSRF bypass, DoS, HTTP smuggling | PR 02 |
| 13 | npm transitive vulnerabilities (Hono, picomatch, etc.) | **LOW** | Dependencies | Low -- mostly dev/transitive deps | PR 02 |
| 14 | Inconsistent version pinning + no Python lock file | **LOW** | Dependency Hygiene | No -- supply-chain drift risk | PR 05 |
| 15 | Railway service IDs in documentation | **INFO** | Information Disclosure | No -- UUIDs, not auth tokens | None (informational) |

---

## 4. Detailed Findings

### Finding #1: Tenant Isolation Bypass via initData Without chat Field [HIGH]

**Location:** `src/api/routes/onboarding/helpers.py:37-44`

When the Telegram Mini App is opened in a private/DM context (not a group chat), the WebApp SDK sends `initData` containing a `user` field but no `chat` field. The `validate_init_data()` function only populates `chat_id` when the `chat` JSON field exists. In `_validate_request()`:

```python
signed_chat_id = user_info.get("chat_id")
if signed_chat_id is not None and signed_chat_id != chat_id:
    raise HTTPException(status_code=403, detail="Chat ID mismatch")
```

When `signed_chat_id` is `None`, the check passes for ANY `chat_id` provided in the request body. This affects all 17 onboarding/dashboard/settings endpoints.

**Impact:** Full cross-tenant data access and modification. An attacker can read queue details, toggle settings (including `dry_run_mode` and `is_paused`), and trigger media sync for any tenant.

---

### Finding #2: Unauthenticated OAuth Start Endpoints [HIGH]

**Location:** `src/api/routes/oauth.py:17-29, 185-197`

The `/auth/instagram/start` and `/auth/google-drive/start` endpoints accept a `chat_id` query parameter with zero authentication:

```python
@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    with OAuthService() as oauth_service, service_error_handler():
        auth_url = oauth_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
```

An attacker calls `GET /auth/instagram/start?chat_id=<VICTIM_CHAT_ID>`, completes OAuth with their own Instagram account, and the callback stores the attacker's credentials as the active account for the victim's chat. Scheduled posts then go to the attacker's Instagram.

**Impact:** Complete Instagram account takeover of any tenant.

---

### Finding #3: cryptography 46.0.3 -- Two CVEs [HIGH]

**Location:** `requirements.txt:38` -- `cryptography>=41.0.0`

- **CVE-2026-26007** (HIGH): Private key leakage when using uncommon binary elliptic curves. Fixed in 46.0.5.
- **CVE-2026-34073** (HIGH): DNS name constraint bypass in certificate validation. Fixed in 46.0.6.

**Current:** 46.0.3 | **Required:** >= 46.0.6

This package handles token encryption and OAuth token security for the Instagram API integration. Both CVEs are exploitable in production.

---

### Finding #4: drizzle-orm SQL Injection in Landing Site [HIGH]

**Location:** `landing/package.json:18` -- `drizzle-orm: "^0.45.1"`

**GHSA-gpj5-g38j-94v9** (HIGH): SQL injection via improperly escaped SQL identifiers. An attacker can inject arbitrary SQL through table/column names. The landing site uses drizzle-orm with Neon PostgreSQL.

**Current:** <0.45.2 | **Required:** >= 0.45.2

---

### Finding #5: Cross-Tenant Account Operations (IDOR) [MEDIUM]

**Location:** `src/api/routes/onboarding/settings.py:99-112` and `src/api/routes/onboarding/dashboard.py:53-84`

- **remove-account:** Validates authentication for `request.chat_id`, then calls `deactivate_account(account_id=request.account_id)` with no check that the account belongs to the requesting chat.
- **accounts list:** Calls `account_service.list_accounts(include_inactive=False)` which returns ALL active accounts across ALL tenants.

**Impact:** Authenticated users can discover and deactivate Instagram accounts belonging to other tenants.

---

### Finding #6: starlette 0.52.1 CORS Misconfiguration CVE [MEDIUM]

**Location:** `requirements.txt:34` -- `fastapi>=0.109.0` (depends on starlette 0.52.1)

**CVE-2026-33010** (MEDIUM): CORS misconfiguration where responses may return `Access-Control-Allow-Origin: *`, overriding application-level restrictions. The codebase already restricts `allow_origins` per security rules, but the underlying framework bug may override this.

**Current:** starlette 0.52.1 | **Latest:** 1.0.0

---

### Finding #7: requests 2.32.5 File Replacement CVE [MEDIUM]

**Location:** `requirements.txt` -- `requests` (transitive or direct)

**CVE-2026-25645** (MEDIUM): `requests.utils.extract_zipped_paths` extracts to a predictable location. Low risk for this project but trivial to update.

**Current:** 2.32.5 | **Latest:** 2.33.1

---

### Finding #8: FastAPI Docs Exposed in Production [MEDIUM]

**Location:** `src/api/app.py:14-18`

The FastAPI app is created without disabling documentation endpoints. `/docs` (Swagger UI), `/redoc`, and `/openapi.json` are publicly accessible at the production Railway URL, exposing the full API schema.

**Impact:** Provides attackers a complete map of the API surface, including all parameter names, types, and endpoint paths.

---

### Finding #9: Missing Security Headers [MEDIUM]

**Location:** `src/api/app.py` -- no security headers middleware

Missing headers:
- **Strict-Transport-Security (HSTS):** Browsers may allow HTTP downgrade attacks.
- **X-Frame-Options:** OAuth callback and onboarding pages could be clickjacked.
- **X-Content-Type-Options:** Missing `nosniff` allows MIME-type confusion.
- **Content-Security-Policy:** No CSP on HTML pages.

---

### Finding #10: No Rate Limiting on API Endpoints [LOW]

**Location:** All routes in `src/api/`

No rate limiting library is installed or configured. All 17+ API endpoints are unthrottled, including OAuth start, state-mutating, and dashboard read endpoints.

**Impact:** Denial-of-service risk and potential for abuse of OAuth flows.

---

### Finding #11: innerHTML Without Escaping on Controlled Data [LOW]

**Location:** `src/api/static/onboarding/app.js:758`

`item.detail` is inserted into HTML via `innerHTML` without `_escapeHtml()`. However, all dynamic values are either escaped at the source or are hardcoded strings. The pattern is fragile but not currently exploitable.

**No PR required** -- informational. Recommend applying `_escapeHtml()` universally in future refactors.

---

### Finding #12: Next.js 16.1.6 -- 5 Moderate Vulnerabilities [LOW]

**Location:** `landing/package.json:20`

Includes HTTP request smuggling, unbounded cache growth DoS, CSRF bypass via null origin, and HMR WebSocket CSRF. Fix: `npm audit fix --force` to upgrade to next@16.2.3.

---

### Finding #13: npm Transitive Vulnerabilities [LOW]

**Location:** `landing/package-lock.json`

13 total npm vulnerabilities (5 HIGH, 8 MODERATE) across transitive dependencies: Hono (prototype pollution, path traversal), express-rate-limit (IPv4-mapped IPv6 bypass), flatted (DoS), path-to-regexp (ReDoS), picomatch (POSIX class injection). Most fixable via `npm audit fix`.

---

### Finding #14: Inconsistent Version Pinning + No Python Lock File [LOW]

**Location:** `requirements.txt`

Mix of exact pins (`==`) and floor pins (`>=`). Notable: `cryptography>=41.0.0`, `fastapi>=0.109.0`, `uvicorn>=0.27.0`. No `requirements.lock` or `pip-compile` output exists, making vulnerability tracking unreliable across environments.

---

### Finding #15: Railway Service IDs in Documentation [INFO]

**Location:** `documentation/archive/callback-reliability_2026-02-25/00_INVESTIGATION.md:11-12`

Railway service UUIDs present in archived documentation. These are low-sensitivity identifiers (not auth tokens) and pose minimal risk.

**No PR required** -- informational only.

---

## 5. Remediation Plan

### Priority Order

Findings are remediated in order of severity and exploitability:

| Priority | PR | Title | Severity | Findings |
|----------|----|-------|----------|----------|
| 1 | **PR 01** | Tenant isolation & OAuth auth bypass | HIGH | #1, #2, #5 |
| 2 | **PR 02** | Vulnerable Python & npm dependencies | HIGH | #3, #6, #7, #12, #13 |
| 3 | **PR 04** | drizzle-orm SQL injection in landing site | HIGH | #4 |
| 4 | **PR 03** | API hardening: docs, headers, rate limiting | MEDIUM | #8, #9, #10 |
| 5 | **PR 05** | Dependency hygiene: pinning & lock file | LOW | #14 |

PRs 01, 02, and 04 address HIGH-severity findings and should be implemented first. PR 03 addresses MEDIUM-severity hardening. PR 05 addresses LOW-severity hygiene and should run last (after PR 02, which changes dependency versions).

---

## 6. PR Grouping Rationale

### PR 01: Tenant Isolation & OAuth Auth Bypass (Findings #1, #2, #5)

**Why grouped:** All three findings share the same root cause -- insufficient authorization checks at the API boundary layer. Finding #1 (tenant bypass via missing chat_id) and #5 (IDOR on account operations) both stem from missing tenant-scoping in `_validate_request()` and downstream service calls. Finding #2 (unauthenticated OAuth start) is the most severe variant -- it requires no authentication at all. Fixing these together ensures consistent tenant boundary enforcement across all API routes in a single pass.

**Files touched:** `src/api/routes/onboarding/helpers.py`, `src/api/routes/oauth.py`, `src/api/routes/onboarding/settings.py`, `src/api/routes/onboarding/dashboard.py`, `src/services/instagram_account_service.py`

---

### PR 02: Vulnerable Python & npm Dependencies (Findings #3, #6, #7, #12, #13)

**Why grouped:** All five findings are dependency version bumps with no application code changes required. Python dependencies (`cryptography`, `starlette`/`fastapi`, `requests`) are updated in `requirements.txt`. npm dependencies (Next.js, Hono, transitive) are updated via `npm audit fix` in `landing/`. Grouping all version bumps in one PR simplifies testing -- run the full test suite once to verify no regressions.

**Files touched:** `requirements.txt`, `landing/package.json`, `landing/package-lock.json`

---

### PR 03: API Hardening -- Docs, Headers, Rate Limiting (Findings #8, #9, #10)

**Why grouped:** All three findings are defense-in-depth measures applied to the same file (`src/api/app.py`) and the same architectural layer (FastAPI middleware/configuration). Disabling docs, adding security headers, and adding rate limiting are all middleware-level changes that don't affect business logic or require service-layer changes. They share the same verification approach (integration tests against the API).

**Files touched:** `src/api/app.py`, new middleware file(s) in `src/api/`

---

### PR 04: drizzle-orm SQL Injection in Landing Site (Finding #4)

**Why isolated:** This finding is in the Next.js landing site (`landing/`), which is a completely separate codebase from the Python backend. It has its own package.json, its own deployment pipeline, and its own test suite. Isolating it avoids any risk of conflating landing site changes with backend changes, and allows the landing site team to review independently.

**Files touched:** `landing/package.json`, `landing/package-lock.json`

---

### PR 05: Dependency Hygiene -- Pinning & Lock File (Finding #14)

**Why last:** This PR pins all `>=` dependencies to exact `==` versions and introduces `pip-compile` (from `pip-tools`) for deterministic dependency locking. It must run after PR 02 because PR 02 changes the target versions of several packages. Running PR 05 first would pin old vulnerable versions; running it after PR 02 ensures the lock file captures the updated, patched versions.

**Files touched:** `requirements.txt`, new `requirements.lock` (or `requirements.txt` generated by pip-compile), `pyproject.toml` or `Makefile` (pip-tools integration)

---

## 7. Dependency Matrix

```
PR 01 (Tenant isolation)  ──┐
                             ├──  Can run in PARALLEL (independent file sets)
PR 02 (Dep versions)     ──┘

PR 03 (API hardening)     ──────  INDEPENDENT (can run anytime)

PR 04 (drizzle-orm)       ──────  INDEPENDENT (separate codebase: landing/)

PR 05 (Dep pinning)       ──────  SEQUENTIAL: must run AFTER PR 02
```

| PR | Depends On | Unlocks | Can Parallel With |
|----|-----------|---------|-------------------|
| 01 | None | -- | 02, 03, 04 |
| 02 | None | 05 | 01, 03, 04 |
| 03 | None | -- | 01, 02, 04, 05 |
| 04 | None | -- | 01, 02, 03, 05 |
| 05 | **02** | -- | 01, 03, 04 |

**Recommended execution order:**
1. Start PR 01 and PR 02 in parallel (both HIGH, independent)
2. Start PR 03 and PR 04 at any time (independent of everything)
3. Start PR 05 only after PR 02 merges

---

## 8. Findings Not Requiring PRs

### Finding #11: innerHTML Without Escaping (LOW)

The `item.detail` values in `app.js:758` bypass `_escapeHtml()`, but all dynamic values are either (a) escaped at the source before assignment to `item.detail`, or (b) hardcoded strings like `'Not connected'`. This is a fragile pattern but not currently exploitable. Recommend applying universal escaping during the next frontend refactor.

### Finding #15: Railway Service IDs in Documentation (INFO)

Railway service UUIDs in `documentation/archive/callback-reliability_2026-02-25/00_INVESTIGATION.md` are low-sensitivity identifiers used for operational reference. They are not authentication tokens and cannot be used to access or modify Railway resources without a valid API token. No action required.

---

## 9. Positive Findings

The audit identified strong security practices across multiple categories:

| Category | Assessment |
|----------|------------|
| **SQL Injection** | All database operations use SQLAlchemy ORM with parameterized queries. No raw SQL with user input. |
| **Command Injection** | No `exec()`, `eval()`, `subprocess`, or `os.system()` usage in `src/`. |
| **Insecure Deserialization** | No `pickle.loads`, no unsafe `yaml.load()`. JSON via Pydantic. |
| **Path Traversal** | File paths from controlled sources only. No user-supplied file paths in API. |
| **XSS (Server-Side)** | Consistent `html.escape()` on all user-supplied values in HTML templates. |
| **CORS** | Properly restricted to `OAUTH_REDIRECT_BASE_URL`. No wildcard `*`. |
| **Token Encryption** | Fernet (AES-128-CBC + HMAC) for API tokens at rest. Key from env vars. |
| **OAuth State Tokens** | Fernet encryption with 10-minute TTL, nonce, and CSRF protection. |
| **initData Validation** | HMAC-SHA256 with `WebAppData` key derivation, constant-time comparison, 1-hour TTL. |
| **Input Validation** | Pydantic `Field(ge=, le=)` on numeric inputs. String length limits and regex patterns. |
| **TLS** | No `verify=False` anywhere. All external calls over HTTPS. |
| **Secret Management** | All secrets via Pydantic Settings. No hardcoded values. `.gitignore` comprehensive. |
| **Telegram Bot** | Uses polling (not webhooks). No webhook endpoint to secure. |
