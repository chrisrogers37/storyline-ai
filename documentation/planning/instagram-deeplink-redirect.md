# Instagram Story Camera Deep Link Redirect Service

**Status**: Planning
**Priority**: High (Backlog item from Phase 1.5)
**Estimated effort**: 1-2 hours
**Date**: 2026-03-08

---

## Problem Statement

When the Telegram bot sends a story notification, the "Open Instagram" button currently links to `https://www.instagram.com/` — which opens the Instagram **feed**, not the story camera. The manual posting workflow requires users to:

1. Save the image from Telegram
2. Open Instagram (via the button — lands on feed)
3. Navigate to the story camera manually
4. Select the saved image
5. Post the story

**Goal**: Replace step 2-3 with a single tap that opens the Instagram **story camera** directly.

### Why Not Just Use `instagram://story-camera`?

Telegram Bot API only allows HTTPS URLs in `InlineKeyboardButton(url=...)`. Custom URL schemes like `instagram://` are rejected by Telegram's API. We need an intermediary HTTPS page that redirects to the custom scheme.

---

## Research Findings

### Instagram URL Schemes (Undocumented but Widely Used)

| Scheme | Purpose | Platform | Status |
|--------|---------|----------|--------|
| `instagram://app` | Opens Instagram | iOS/Android | Working |
| `instagram://camera` | Opens camera | iOS/Android | Working |
| `instagram://story-camera` | Opens story camera | iOS/Android | Likely working (used by URLgenius, JotURL) |
| `instagram://user?username=X` | Opens profile | iOS/Android | Working |
| `instagram://media?id=X` | Opens specific post | iOS/Android | Working |

**Important caveats**:
- These are **undocumented** by Meta — they could break without notice
- No official Meta documentation confirms `instagram://story-camera` specifically
- Deep linking tools (URLgenius, JotURL) actively advertise story camera deep linking, suggesting it works
- Community-maintained lists (GitHub, DEV Community) confirm `instagram://camera` at minimum

### Web URL Alternatives

| URL | Behavior |
|-----|----------|
| `https://www.instagram.com/` | Opens feed (current behavior) |
| `https://www.instagram.com/stories/create/` | May redirect to story camera on mobile (unconfirmed reliability) |
| `https://www.instagram.com/{username}/` | Opens profile |

### The Redirect Page Technique

A simple static HTML page can bridge HTTPS → custom scheme:

```html
<script>
  // Try to open Instagram story camera via custom scheme
  window.location.href = "instagram://story-camera";

  // Fallback: if app not installed, redirect to Instagram web after 1.5s
  setTimeout(() => {
    window.location.href = "https://www.instagram.com/";
  }, 1500);
</script>
```

**How it works**:
1. User taps "Open Instagram" button in Telegram
2. Telegram opens the HTTPS URL (our redirect page)
3. Page immediately tries `instagram://story-camera`
4. If Instagram app is installed → app opens to story camera
5. If not installed → after 1.5s timeout, falls back to Instagram web

**Known issues**:
- iOS Safari may show a "Open in Instagram?" confirmation dialog (expected, not a problem)
- Android Chrome handles custom schemes transparently
- If Instagram is not installed, user briefly sees the redirect page before fallback
- Instagram's in-app browser may not support custom schemes (not relevant — we're coming from Telegram, not Instagram)

### GitHub Pages Viability

GitHub Pages is an ideal host for this:
- Free, no infrastructure to maintain
- Serves from the same repo (e.g., `docs/` folder or `gh-pages` branch)
- HTTPS by default (required by Telegram)
- Custom domain support if needed
- No CORS/CSP restrictions for JavaScript redirects
- Static HTML only — perfect for a simple redirect page

---

## Proposed Implementation

### Architecture

```
Telegram Bot                    GitHub Pages                    Instagram App
┌──────────────┐               ┌──────────────┐               ┌──────────────┐
│ [📱 Open     │  HTTPS tap    │  Redirect    │  instagram:// │  Story       │
│  Instagram]  │ ────────────► │  Page        │ ────────────► │  Camera      │
│              │               │  (static)    │               │              │
└──────────────┘               └──────────────┘               └──────────────┘
                                     │ 1.5s timeout
                                     ▼
                               ┌──────────────┐
                               │  Instagram   │
                               │  Web (feed)  │
                               └──────────────┘
```

### File Structure

```
docs/                          ← GitHub Pages source directory
├── index.html                 ← Main redirect page (story camera)
├── profile.html               ← Profile redirect (future use)
└── 404.html                   ← Catch-all fallback
```

Using the `docs/` folder approach (vs `gh-pages` branch) keeps everything in the main branch and is simpler to maintain.

### Redirect Page Design (`docs/index.html`)

**Requirements**:
1. Immediately attempt `instagram://story-camera` redirect
2. Show a brief "Opening Instagram..." message while redirecting
3. Fall back to `https://www.instagram.com/` after timeout
4. Device detection: use `instagram://story-camera` on mobile, skip redirect on desktop
5. Clean, branded appearance (in case user sees the page briefly)
6. No external dependencies (no JS libraries, no CDN)

**Enhanced approach with device detection**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opening Instagram...</title>
  <style>
    /* Minimal loading UI */
  </style>
</head>
<body>
  <div class="container">
    <p>Opening Instagram...</p>
    <p class="fallback" style="display:none">
      <a href="https://www.instagram.com/">Tap here if Instagram didn't open</a>
    </p>
  </div>
  <script>
    (function() {
      var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      var fallbackUrl = "https://www.instagram.com/";
      var deepLink = "instagram://story-camera";

      if (isMobile) {
        // Try deep link
        window.location.href = deepLink;

        // Show fallback link after delay
        setTimeout(function() {
          document.querySelector('.fallback').style.display = 'block';
        }, 1500);

        // Auto-fallback after longer delay
        setTimeout(function() {
          window.location.href = fallbackUrl;
        }, 3000);
      } else {
        // Desktop: go straight to Instagram web
        window.location.href = fallbackUrl;
      }
    })();
  </script>
</body>
</html>
```

### Query Parameter Support (Enhancement)

Support optional parameters via URL query strings for flexibility:

```
https://<username>.github.io/storyline-ai/?action=story-camera    (default)
https://<username>.github.io/storyline-ai/?action=camera
https://<username>.github.io/storyline-ai/?action=profile&user=mybrand
```

This makes the redirect page reusable for different Instagram actions without deploying new pages.

### Code Changes

**Files to modify** (3 files, ~1 line each):

1. **`src/services/core/telegram_utils.py`** (lines 177, 222-223)
   - Change `url="https://www.instagram.com/"` → `url="https://<username>.github.io/storyline-ai/"`

2. **`src/services/core/telegram_notification.py`** (lines 217-218)
   - Same URL change

3. **`src/config/settings.py`** (add new setting)
   - Add `INSTAGRAM_DEEPLINK_URL` setting with `.env` fallback
   - Default: `https://www.instagram.com/` (backward compatible)

4. **`.env.example`** (add documentation)
   - Add `INSTAGRAM_DEEPLINK_URL` example

**Files to create**:

5. **`docs/index.html`** — The redirect page
6. **`docs/404.html`** — Fallback page (optional)

### GitHub Pages Setup

One-time setup steps:
1. Create `docs/` directory with `index.html`
2. Go to repo Settings → Pages → Source: "Deploy from branch" → Branch: `main`, folder: `/docs`
3. Wait for deployment (~1 min)
4. Note the URL: `https://<username>.github.io/storyline-ai/`
5. Update `.env` with the URL

### Configuration

```bash
# .env
# URL for Instagram deep link redirect page (GitHub Pages)
# Default: https://www.instagram.com/ (opens feed, no deep link)
INSTAGRAM_DEEPLINK_URL=https://<username>.github.io/storyline-ai/
```

---

## Testing Plan

### Manual Testing (Required)

| Test | Expected Result | Platform |
|------|----------------|----------|
| Tap "Open Instagram" from Telegram on iPhone | Opens redirect page → Instagram story camera opens | iOS |
| Tap "Open Instagram" from Telegram on Android | Opens redirect page → Instagram story camera opens | Android |
| Tap "Open Instagram" without Instagram installed | Shows fallback link, then redirects to instagram.com | Mobile |
| Tap "Open Instagram" from desktop Telegram | Goes directly to instagram.com | Desktop |
| Visit redirect page directly in browser | Shows "Opening Instagram..." message | Any |

### Unit Tests

Update existing tests that assert `url="https://www.instagram.com/"`:
- `tests/src/services/test_telegram_notification.py` (line 478)
- `tests/src/services/test_telegram_service.py` (lines 168, 567)

These should assert against the configurable `INSTAGRAM_DEEPLINK_URL` setting instead of a hardcoded URL.

---

## Rollback Plan

If the deep link redirect causes issues:
1. Set `INSTAGRAM_DEEPLINK_URL=https://www.instagram.com/` in `.env`
2. Redeploy — reverts to current behavior instantly
3. No code changes needed for rollback

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `instagram://story-camera` stops working | Low | Medium | Fallback to instagram.com after timeout |
| GitHub Pages goes down | Very Low | Low | Setting-based URL allows quick swap to any host |
| User sees redirect page briefly | Expected | Low | Clean "Opening Instagram..." UI |
| Telegram blocks the redirect URL | Very Low | High | URL is standard HTTPS, no reason to block |
| iOS confirmation dialog ("Open in Instagram?") | Expected | None | Standard iOS behavior, one tap to confirm |

---

## Future Enhancements (Out of Scope)

These are potential improvements but should NOT be included in the initial implementation:

1. **Analytics**: Add a simple page view counter (e.g., Plausible, or a 1x1 pixel to a tracking endpoint)
2. **Custom domain**: Use a branded domain instead of github.io
3. **Additional redirect targets**: Profile page, DMs, specific posts
4. **A/B testing**: Test `instagram://story-camera` vs `instagram://camera` to see which has better success rates
5. **Smart fallback**: Detect if Instagram opened successfully (tricky, uses `visibilitychange` event)

---

## Sources

- [Instagram URL Schemes (community list)](https://github.com/Tanaschita/ios-known-url-schemes-and-universal-links)
- [Instagram Story Camera Deep Links (URLgenius)](https://app.urlgeni.us/blog/introducing-instagram-story-camera-deep-links)
- [Instagram Deep Link Guide (JotURL)](https://joturl.com/blog/easiest-way-to-deep-link-to-instagram)
- [Deep Link Instagram (Gist)](https://gist.github.com/juniorthiesen/d2a8162e3a51b25dd2f8cf2ba921c018)
- [Social Deep Link Redirecting for GitHub Pages](https://github.com/Camprowe/social-deep-link-redirecting)
- [Universal Link + URL Scheme from Instagram Stories (Medium)](https://medium.com/@cemnisan/how-to-automatically-open-your-app-from-instagram-stories-using-universal-link-and-url-scheme-71650ee90a8b)
- [Instagram Deep Link Guide (Replug)](https://blog.replug.io/instagram-deep-link/)

---

## Implementation Checklist

- [ ] Create `docs/index.html` redirect page
- [ ] Create `docs/404.html` fallback page
- [ ] Add `INSTAGRAM_DEEPLINK_URL` to `src/config/settings.py`
- [ ] Add `INSTAGRAM_DEEPLINK_URL` to `.env.example`
- [ ] Update `telegram_utils.py` to use configurable URL
- [ ] Update `telegram_notification.py` to use configurable URL
- [ ] Update tests to use configurable URL
- [ ] Enable GitHub Pages on repo (manual step)
- [ ] Test on iOS device
- [ ] Test on Android device
- [ ] Test desktop fallback
- [ ] Update CHANGELOG.md
