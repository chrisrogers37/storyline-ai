# Instagram API Setup Guide

This guide walks you through setting up Instagram API integration for automated Story posting. Meta's developer platform can be challenging to navigate - this guide documents the exact steps and common pitfalls.

---

## Prerequisites

Before you begin, ensure you have:

1. **Instagram Business or Creator Account** - Personal accounts are NOT supported
2. **Facebook Page** linked to your Instagram account
3. **Meta Business Suite** account with your Page and Instagram connected
4. **Meta Developer Account** at [developers.facebook.com](https://developers.facebook.com)
5. **Cloudinary Account** for media hosting (free tier available)

---

## Overview

The Instagram Content Publishing API works **through Facebook's Graph API**, not Instagram's directly:

| API | Endpoint | Purpose |
|-----|----------|---------|
| Instagram Basic Display API | `graph.instagram.com` | Read-only access to personal accounts (no posting) |
| **Instagram Graph API (Content Publishing)** | `graph.facebook.com` | **Posting to Business/Creator accounts** |

**Key concept:** You authenticate with a Facebook Page Access Token, then use your Instagram Business Account ID to post Stories.

---

## Step 1: Set Up Meta Business Suite

Before touching the Developer Portal, ensure your accounts are properly linked in Meta Business Suite.

1. Go to [business.facebook.com](https://business.facebook.com)
2. Create a Business Portfolio if you don't have one
3. Add your Facebook Page to the portfolio
4. Connect your Instagram Business account to the Page:
   - Go to your Facebook Page → Settings → Instagram
   - Click "Connect Account" and authorize

**Verify the connection:**
- In Meta Business Suite, you should see both your Page and Instagram account listed under "Profiles"

---

## Step 2: Convert Instagram to Business/Creator Account

If your Instagram account is still "Personal":

1. Open Instagram app
2. Go to Settings → Account → Switch to Professional Account
3. Choose "Business" or "Creator"
4. Connect to your Facebook Page when prompted

---

## Step 3: Create a Meta Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps** → **Create App**
3. Select **"Other"** for use case, then **"Business"** as app type
4. Enter app details:
   - **App Name**: e.g., "Story Poster"
   - **Contact Email**: your email
5. Click **Create App**

### Troubleshooting: "You don't have access"

If you see "This feature isn't available to you yet":

1. Go to [developers.facebook.com/async/registration/](https://developers.facebook.com/async/registration/) to register as a developer
2. Verify your Facebook account (email + phone)
3. Enable Two-Factor Authentication on Facebook
4. Try accessing through [business.facebook.com](https://business.facebook.com) first
5. Clear cookies and try in an incognito window

---

## Step 4: Configure App Settings

### Get App Credentials

1. Go to **Settings** → **Basic**
2. Note your:
   - **App ID**: e.g., `1234567890123456`
   - **App Secret**: Click "Show" to reveal

Add to your `.env`:
```bash
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
```

### Add Instagram Graph API Product

1. From your app dashboard, click **Add Product**
2. Find **"Instagram Graph API"** and click **Set Up**
3. Complete the basic setup wizard

---

## Step 5: Add Instagram Testers

**Critical step** - Without this, you'll get "Insufficient Developer Role" errors.

1. In your app, go to **App Roles** → **Roles**
2. Find **"Instagram Testers"** section
3. Click **Add Instagram Testers**
4. Enter the **Instagram username** (not Facebook name) of the account you want to use
5. Click **Submit**

### Accept the Tester Invite

The Instagram account owner must accept the invite:

1. Open **Instagram** (app or web)
2. Go to **Settings** → **Website Permissions** → **Apps and Websites**
3. Look for **"Tester Invites"** tab
4. **Accept** the invite from your app

**Note:** This is different from Facebook app testers. Instagram has its own tester system.

---

## Step 6: Get Access Tokens via Graph API Explorer

This is the trickiest part. Follow these steps exactly.

### Open Graph API Explorer

Go to: [developers.facebook.com/tools/explorer/](https://developers.facebook.com/tools/explorer/)

### Generate User Access Token

1. **Meta App dropdown** → Select your app
2. **User or Page dropdown** → Click **"Get User Access Token"**
3. **Add permissions** (check these boxes):
   - `pages_show_list`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
   - `business_management`
4. Click **"Generate Access Token"**
5. Log in and authorize when prompted

### Find Your Instagram Account ID

**Important:** Make sure the endpoint dropdown shows `graph.facebook.com` (NOT `graph.instagram.com`)

Run this query:
```
me/businesses?fields=name,owned_pages{name,instagram_business_account{id,username}}
```

You'll get a response like:
```json
{
  "data": [
    {
      "name": "Your Business",
      "owned_pages": {
        "data": [
          {
            "name": "Your Page",
            "instagram_business_account": {
              "id": "12345678901234567",
              "username": "youraccount"
            },
            "id": "123456789012345"
          }
        ]
      }
    }
  ]
}
```

Note down:
- **Instagram Business Account ID**: `12345678901234567` (this goes in `INSTAGRAM_ACCOUNT_ID`)
- **Facebook Page ID**: `123456789012345` (used to get Page Access Token)

### Troubleshooting: Empty Response

If `me/accounts` returns empty `{"data": []}`:

- Your Pages are likely in a **Business Portfolio**, not your personal account
- Use the `me/businesses?fields=...` query instead
- Make sure you have `business_management` permission

### Extend User Token (Make it Long-Lived)

The user token expires in ~1 hour. Extend it:

1. Go to [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
2. Paste your User Access Token
3. Click **Debug**
4. Click **"Extend Access Token"** at the bottom
5. Copy the new long-lived token (expires in ~60 days)

### Get Page Access Token

With your **long-lived user token** in Graph API Explorer, query:

```
YOUR_PAGE_ID?fields=access_token,name
```

Example:
```
123456789012345?fields=access_token,name
```

The Page Access Token you receive will be **permanent** (never expires) because it was derived from a long-lived user token.

### Verify Token is Permanent

1. Go to [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
2. Paste the Page Access Token
3. Click **Debug**
4. Confirm it shows **"Expires: Never"**

---

## Step 7: Set Up Cloudinary

Instagram requires media to be hosted at a public URL. We use Cloudinary for this.

1. Create account at [cloudinary.com](https://cloudinary.com) (free tier works)
2. Go to **Dashboard**
3. Note your credentials

Add to `.env`:
```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your_api_secret
```

---

## Step 8: Generate Encryption Key

The system encrypts tokens before storing them in the database.

```bash
source venv/bin/activate
python -c "from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())"
```

Add to `.env`:
```bash
ENCRYPTION_KEY=your_generated_key_here
```

---

## Step 9: Run Database Migration

Apply the Phase 2 database changes:

```bash
psql -U your_user -d storyline_ai -f scripts/migrations/004_instagram_api_phase2.sql
```

Verify:
```bash
psql -U your_user -d storyline_ai -c "SELECT * FROM schema_version ORDER BY version;"
```

---

## Step 10: Complete Your .env Configuration

```bash
# ============================================
# Phase Control
# ============================================
ENABLE_INSTAGRAM_API=true

# ============================================
# Instagram API Configuration
# ============================================
INSTAGRAM_ACCOUNT_ID=12345678901234567
INSTAGRAM_ACCESS_TOKEN=EAAXXX...your_page_access_token...

# Facebook App (for future token refresh)
FACEBOOK_APP_ID=1234567890123456
FACEBOOK_APP_SECRET=your_app_secret

# ============================================
# Cloudinary Configuration
# ============================================
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your_api_secret

# ============================================
# Security
# ============================================
ENCRYPTION_KEY=your_fernet_key
```

---

## Step 11: Bootstrap Token and Verify

Run the setup test:

```bash
source venv/bin/activate
python << 'EOF'
from src.services.integrations.instagram_api import InstagramAPIService
from src.services.integrations.token_refresh import TokenRefreshService
from src.config.settings import settings

print("=== Instagram API Setup Test ===\n")

print(f"ENABLE_INSTAGRAM_API: {settings.ENABLE_INSTAGRAM_API}")
print(f"INSTAGRAM_ACCOUNT_ID: {settings.INSTAGRAM_ACCOUNT_ID}")
print(f"Token configured: {'Yes' if settings.INSTAGRAM_ACCESS_TOKEN else 'No'}")

ig_service = InstagramAPIService()
print(f"\nis_configured(): {ig_service.is_configured()}")
print(f"Rate limit: {ig_service.get_rate_limit_status()}")

# Bootstrap token to database
token_service = TokenRefreshService()
result = token_service.bootstrap_from_env("instagram")
print(f"\nToken bootstrapped: {result}")

health = token_service.check_token_health("instagram")
print(f"Token valid: {health.get('valid')}")
print(f"Expires in hours: {health.get('expires_in_hours', 'N/A')}")
EOF
```

Expected output:
```
ENABLE_INSTAGRAM_API: True
INSTAGRAM_ACCOUNT_ID: 12345678901234567
Token configured: Yes

is_configured(): True
Rate limit: {'remaining': 25, 'limit': 25, 'used': 0, 'window': '1 hour'}

Token bootstrapped: True
Token valid: True
Expires in hours: 1440
```

---

## Step 12: Test Posting (Optional)

Once verified, test with `DRY_RUN_MODE=true` first:

```bash
# In .env
DRY_RUN_MODE=true
```

Then:
```bash
storyline-cli process-queue --force
```

When ready for real posting, set `DRY_RUN_MODE=false`.

---

## Troubleshooting

### "Insufficient Developer Role" Error

**Cause:** Instagram account not added as Instagram Tester, or invite not accepted.

**Fix:**
1. Add Instagram username as Instagram Tester in app roles
2. Accept invite: Instagram → Settings → Website Permissions → Apps and Websites → Tester Invites

### "Invalid OAuth access token - Cannot parse access token"

**Cause:** Token is malformed, has extra spaces, or wrong token type.

**Fix:**
1. Make sure endpoint is `graph.facebook.com` (not `graph.instagram.com`)
2. Clear the token field and regenerate
3. Check for extra spaces or line breaks in the token

### Empty Response from `me/accounts`

**Cause:** Pages are in a Business Portfolio, not directly owned by your Facebook account.

**Fix:** Query through businesses instead:
```
me/businesses?fields=name,owned_pages{name,instagram_business_account{id,username}}
```

### "Error validating application"

**Cause:** Wrong App ID or App Secret.

**Fix:** Verify credentials in Settings → Basic match your `.env` file.

### Token Expires in 1 Hour

**Cause:** Using short-lived token.

**Fix:**
1. Extend User Token via Access Token Debugger
2. Then get Page Access Token using the extended token
3. Page tokens derived from long-lived user tokens are permanent

### Rate Limit Errors

Instagram allows ~25 content publishing calls per hour.

**Behavior:** System automatically falls back to Telegram when rate limited.

**Check status:**
```bash
storyline-cli check-health
```

### "No Instagram Business Account" Error

**Fix:**
1. Convert Instagram to Business or Creator account
2. Link it to a Facebook Page
3. Ensure Page is in your Business Portfolio

---

## Understanding the Token Hierarchy

```
Facebook User Account
    └── Long-Lived User Token (60 days)
            └── Facebook Page
                    └── Page Access Token (permanent)
                            └── Instagram Business Account
                                    └── Can post Stories!
```

The Page Access Token is what you store in `INSTAGRAM_ACCESS_TOKEN`. It:
- Never expires (when derived from long-lived user token)
- Has permissions to post to the connected Instagram account
- Is tied to a specific Facebook Page

---

## Multiple Instagram Accounts

To manage multiple accounts, you can store alternate credentials commented out:

```bash
# Currently active: Account A
INSTAGRAM_ACCOUNT_ID=12345678901234567
INSTAGRAM_ACCESS_TOKEN=EAAXXX...your_token_here...

# Alternate: Account B
# INSTAGRAM_ACCOUNT_ID=98765432109876543
# INSTAGRAM_ACCESS_TOKEN=EAAXXX...alternate_token_here...
```

Swap which lines are commented to switch accounts.

---

## Security Notes

1. **Never commit `.env`** to version control
2. **Page tokens are permanent** - treat them like passwords
3. **Backup your encryption key** - losing it means re-bootstrapping tokens
4. **App is in Development Mode** - only testers can use it (which is fine for self-hosting)

---

## Quick Reference

| Item | Where to Find It |
|------|------------------|
| App ID | Meta Developer → Your App → Settings → Basic |
| App Secret | Meta Developer → Your App → Settings → Basic |
| Instagram Account ID | Graph API Explorer query (see Step 6) |
| Page Access Token | Graph API Explorer query (see Step 6) |
| Cloudinary credentials | Cloudinary Dashboard |

| Endpoint | Purpose |
|----------|---------|
| `graph.facebook.com` | All posting operations |
| `graph.instagram.com` | Don't use for posting |

| Tool | URL |
|------|-----|
| Graph API Explorer | developers.facebook.com/tools/explorer/ |
| Access Token Debugger | developers.facebook.com/tools/debug/accesstoken/ |
| Meta Business Suite | business.facebook.com |
