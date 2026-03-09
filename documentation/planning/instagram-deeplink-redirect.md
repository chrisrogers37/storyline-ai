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

**Additional schemes** (from research):

| Scheme | Purpose | Platform | Status |
|--------|---------|----------|--------|
| `instagram://location?id=X` | Opens location page | iOS/Android | Working |
| `instagram://settings` | Opens settings | iOS/Android | Working |
| `instagram-stories://share?source_application=X` | Share to Stories (native only) | iOS | Official Meta SDK |

**Important caveats**:
- These are **undocumented** by Meta — they could break without notice
- No official Meta documentation confirms `instagram://story-camera` specifically
- Deep linking tools (URLgenius, JotURL) actively advertise story camera deep linking, suggesting it works
- Community-maintained lists (GitHub, DEV Community) confirm `instagram://camera` at minimum
- No deprecation reports found for any of these schemes as of March 2026

### Web URL Alternatives

| URL | Behavior |
|-----|----------|
| `https://www.instagram.com/` | Opens feed (current behavior) |
| `https://www.instagram.com/stories/create/` | **Does NOT work** as a deep link — story camera is app-only with no web equivalent |
| `https://www.instagram.com/{username}/` | Opens profile (may open in app via Universal Links on mobile) |

**Key finding**: There is **no web URL that opens the story creation flow**. The story camera is exclusively an app feature. A redirect page with custom URL scheme is the only option.

### Instagram Share to Stories (Official API — Not Applicable)

Meta's official "Sharing to Stories" SDK (`instagram-stories://share`) requires a **native iOS/Android app** as the source. It uses `UIPasteboard` (iOS) or Android Intents to pass image data. There is **no web/JavaScript equivalent** — from a web context, we can only open the story camera, not pre-populate it with an image. This confirms the redirect page approach is the right solution for our use case.

### The Redirect Page Technique

A static HTML page bridges HTTPS → custom scheme. **However, iOS and Android require different approaches**:

**iOS**: `instagram://story-camera` works via `window.location.href`, but if Instagram is NOT installed, Safari shows an alert: *"Safari cannot open the page because the address is invalid."* There is no way to suppress this.

**Android**: Chrome 25+ **dropped support** for direct custom scheme redirects via JavaScript. The `intent://` syntax must be used instead:
```
intent://story-camera#Intent;scheme=instagram;package=com.instagram.android;S.browser_fallback_url=https%3A%2F%2Fwww.instagram.com%2F;end
```
The `intent://` format includes a built-in `browser_fallback_url` that Chrome uses automatically when the app is not installed — no timeout hack needed.

**How it works**:
1. User taps "Open Instagram" button in Telegram
2. Telegram opens the HTTPS URL (our redirect page)
3. Page detects platform (iOS vs Android vs Desktop)
4. **iOS**: Redirects via `instagram://story-camera` with timeout fallback
5. **Android**: Redirects via `intent://` URL (Chrome handles fallback natively)
6. **Desktop**: Goes straight to `instagram.com`

**Known issues**:
- **iOS Safari**: If app not installed, shows "invalid address" alert before fallback fires (unavoidable)
- **iOS Safari**: The `setTimeout` fallback may still fire even after app opens (double-redirect). Mitigation: use `visibilitychange`/`pagehide` events to cancel the fallback timer
- **Android Chrome**: `instagram://` scheme does NOT work — must use `intent://` syntax
- If Instagram is not installed, user briefly sees the redirect page before fallback
- Coming from Telegram (not Instagram's in-app browser), so in-app browser restrictions don't apply

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

**Platform-aware approach (recommended)**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opening Instagram...</title>
  <style>
    body { font-family: -apple-system, system-ui, sans-serif; text-align: center; padding: 60px 20px; }
    .container { max-width: 400px; margin: 0 auto; }
    .fallback { display: none; margin-top: 20px; }
    .fallback a { color: #0095f6; text-decoration: none; font-size: 16px; }
  </style>
</head>
<body>
  <div class="container">
    <p>Opening Instagram Stories...</p>
    <p class="fallback">
      <a href="https://www.instagram.com/">Tap here if Instagram didn't open</a>
    </p>
  </div>
  <script>
    (function() {
      var ua = navigator.userAgent || '';
      var isAndroid = /android/i.test(ua);
      var isIOS = /iphone|ipad|ipod/i.test(ua);
      var fallbackUrl = "https://www.instagram.com/";
      var fallbackTimer;

      if (isAndroid) {
        // Android: Use intent:// syntax (required for Chrome 25+)
        // browser_fallback_url handles app-not-installed case natively
        window.location.href = 'intent://story-camera#Intent;scheme=instagram;package=com.instagram.android;S.browser_fallback_url=' + encodeURIComponent(fallbackUrl) + ';end';
      } else if (isIOS) {
        // iOS: Use custom scheme with visibility-aware fallback
        window.location.href = "instagram://story-camera";

        // Cancel fallback if page becomes hidden (app opened successfully)
        document.addEventListener('visibilitychange', function() {
          if (document.hidden) { clearTimeout(fallbackTimer); }
        });
        document.addEventListener('pagehide', function() {
          clearTimeout(fallbackTimer);
        });

        // Show manual fallback link after 1.5s
        setTimeout(function() {
          document.querySelector('.fallback').style.display = 'block';
        }, 1500);

        // Auto-fallback after 3s if app didn't open
        fallbackTimer = setTimeout(function() {
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

**Key improvements over the naive approach**:
- **Android**: Uses `intent://` syntax required by Chrome, with built-in `browser_fallback_url`
- **iOS**: Uses `visibilitychange`/`pagehide` events to cancel the fallback timer when the app opens successfully (prevents double-redirect)
- **Desktop**: Skips the deep link attempt entirely

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
| `instagram://story-camera` stops working | Low | Medium | Fallback to instagram.com after timeout; can switch to `instagram://camera` |
| GitHub Pages goes down | Very Low | Low | Setting-based URL allows quick swap to any host |
| User sees redirect page briefly | Expected | Low | Clean "Opening Instagram..." UI |
| Telegram blocks the redirect URL | Very Low | High | URL is standard HTTPS, no reason to block |
| iOS "invalid address" alert (app not installed) | Medium | Low | Only affects users without Instagram installed (unlikely for our use case); auto-fallback fires after alert dismissed |
| iOS double-redirect (fallback fires after app opens) | Medium | Medium | `visibilitychange`/`pagehide` event listeners cancel fallback timer |
| Android `instagram://` fails in Chrome | **Confirmed** | High | Use `intent://` syntax with `browser_fallback_url` (required for Chrome 25+) |

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

### URL Schemes & Deep Linking
- [Instagram URL Schemes - DEV Community](https://dev.to/ahandsel/instagram-url-schemes-1k6n)
- [iOS Known URL Schemes & Universal Links (community list)](https://github.com/Tanaschita/ios-known-url-schemes-and-universal-links)
- [Instagram Story Camera Deep Links (URLgenius)](https://app.urlgeni.us/blog/introducing-instagram-story-camera-deep-links)
- [Instagram Story Camera Deep Linking (JotURL)](https://joturl.com/blog/instagram-story-camera-deep-link)
- [Instagram Deep Link Guide (Replug)](https://blog.replug.io/instagram-deep-link/)

### Redirect Technique & Fallback Handling
- [Deep Link Instagram (Gist - redirect snippet)](https://gist.github.com/juniorthiesen/d2a8162e3a51b25dd2f8cf2ba921c018)
- [Deep link to native app from browser with fallback (Gist)](https://gist.github.com/diachedelic/0d60233dab3dcae3215da8a4dfdcd434)
- [Universal Link + URL Scheme from Instagram Stories (Medium, Feb 2024)](https://medium.com/@cemnisan/how-to-automatically-open-your-app-from-instagram-stories-using-universal-link-and-url-scheme-71650ee90a8b)
- [Open Android Apps from Instagram Webview (Medium, Dec 2024)](https://medium.com/@python-javascript-php-html-css/how-to-open-android-apps-from-instagram-webview-using-javascript-7a6facc012a9)

### GitHub Pages Hosting
- [Social Deep Link Redirecting for GitHub Pages](https://github.com/Camprowe/social-deep-link-redirecting)
- [Setup a redirect on GitHub Pages (DEV)](https://dev.to/steveblue/setup-a-redirect-on-github-pages-1ok7)

### Official Meta Documentation
- [Sharing to Stories - Meta for Developers](https://developers.facebook.com/docs/instagram-platform/sharing-to-stories/) (native SDK only, not applicable to web)

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
