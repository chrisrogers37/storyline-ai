# Instagram API Setup Guide

This guide walks you through setting up Instagram API integration for automated Story posting.

## Prerequisites

Before you begin, ensure you have:

1. **Instagram Business or Creator Account** - Personal accounts are not supported
2. **Facebook Page** linked to your Instagram account
3. **Meta Developer Account** at [developers.facebook.com](https://developers.facebook.com)
4. **Cloudinary Account** for media hosting (free tier available)

---

## Step 1: Create a Meta App

1. Go to [Meta for Developers](https://developers.facebook.com)
2. Click **My Apps** > **Create App**
3. Select **Business** as the app type
4. Enter app details:
   - **App Name**: e.g., "Storyline AI"
   - **App Contact Email**: your email
5. Click **Create App**

### Add Instagram Graph API

1. From your app dashboard, click **Add Product**
2. Find **Instagram Graph API** and click **Set Up**
3. The product will be added to your app

---

## Step 2: Configure App Settings

### Get App Credentials

1. Go to **Settings** > **Basic**
2. Note your:
   - **App ID**: e.g., `123456789012345`
   - **App Secret**: Click "Show" to reveal

Add these to your `.env` file:

```bash
FACEBOOK_APP_ID=123456789012345
FACEBOOK_APP_SECRET=your_app_secret_here
```

### Set Up App Permissions

1. Go to **App Review** > **Permissions and Features**
2. Request access for:
   - `instagram_basic` - Required
   - `instagram_content_publish` - Required for posting
   - `pages_show_list` - Required
   - `pages_read_engagement` - Required

For development, these permissions are available in "Development Mode" without review.

---

## Step 3: Link Instagram Account to Facebook Page

1. Go to your **Facebook Page**
2. Click **Settings** > **Instagram**
3. Click **Connect Account**
4. Log in to Instagram and authorize

---

## Step 4: Set Up Cloudinary

1. Create account at [cloudinary.com](https://cloudinary.com)
2. Go to **Dashboard**
3. Note your:
   - **Cloud Name**
   - **API Key**
   - **API Secret**

Add to `.env`:

```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your_api_secret_here
```

---

## Step 5: Generate Encryption Key

The system encrypts tokens before storing them in the database. Generate a key:

```bash
python -c "from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())"
```

Add to `.env`:

```bash
ENCRYPTION_KEY=your_generated_key_here
```

---

## Step 6: Run Database Migration

Apply the Phase 2 database changes:

```bash
psql -U storyline_user -d storyline_ai -f scripts/migrations/004_instagram_api_phase2.sql
```

Verify the migration:

```bash
psql -U storyline_user -d storyline_ai -c "SELECT * FROM schema_version ORDER BY version;"
```

---

## Step 7: Authenticate with Instagram

### Option A: CLI Wizard (Recommended)

Run the authentication wizard:

```bash
storyline-cli instagram-auth
```

The wizard will:
1. Open the Meta Graph API Explorer in your browser
2. Guide you to generate an access token
3. Exchange it for a long-lived token (60 days)
4. Store it securely in the database

### Option B: Manual Authentication

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the dropdown
3. Click **Generate Access Token**
4. Grant these permissions when prompted:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
5. Copy the generated token
6. Run: `storyline-cli instagram-auth`
7. Paste the token when prompted

---

## Step 8: Get Instagram Account ID

After authentication, note the Instagram Account ID displayed.

Add to `.env`:

```bash
INSTAGRAM_ACCOUNT_ID=17841400000000000
```

Or run:

```bash
storyline-cli instagram-status
```

---

## Step 9: Enable Instagram API

Update your `.env`:

```bash
ENABLE_INSTAGRAM_API=true
```

---

## Step 10: Verify Setup

Run health check:

```bash
storyline-cli check-health
```

You should see:

```
Instagram Api: OK (25/25 posts remaining)
```

Check detailed status:

```bash
storyline-cli instagram-status
```

---

## Complete .env Configuration

Here's a complete example of Phase 2 settings:

```bash
# Phase 2 Feature Flag
ENABLE_INSTAGRAM_API=true

# Instagram API
INSTAGRAM_ACCOUNT_ID=17841400000000000
FACEBOOK_APP_ID=123456789012345
FACEBOOK_APP_SECRET=abc123...

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=abc123...

# Security
ENCRYPTION_KEY=your_fernet_key_here
```

---

## Troubleshooting

### Token Expired

If your token expires (after 60 days without refresh):

1. Run `storyline-cli instagram-auth` again
2. Generate a new token in Graph API Explorer
3. The system will store the new token

### Rate Limit Errors

Instagram allows ~25 content publishing calls per hour. If you hit limits:

- The system automatically falls back to Telegram
- Wait an hour for the limit to reset
- Check rate limit status: `storyline-cli check-health`

### "No Instagram Business Account" Error

Ensure:
1. Your Instagram account is Business or Creator type
2. It's linked to a Facebook Page
3. You've granted permissions in the Facebook app

### Cloudinary Upload Failures

Check:
1. Credentials are correct in `.env`
2. Image meets Instagram requirements (see below)
3. File size is under 100MB

---

## Instagram Story Requirements

Stories must meet these specifications:

| Requirement | Specification |
|-------------|---------------|
| Aspect Ratio | 9:16 (recommended), 1.91:1 to 9:16 (accepted) |
| Resolution | 1080x1920 (recommended), min 720x1280 |
| File Size | Max 100MB |
| Formats | JPG, PNG, GIF (images), MP4, MOV (video) |
| Video Length | 1-60 seconds |

The system validates media before uploading. Use:

```bash
storyline-cli validate /path/to/image.jpg
```

---

## Security Notes

1. **Never commit `.env`** to version control
2. **Rotate tokens** if compromised
3. **Backup encryption key** - losing it means re-authenticating
4. **Use app in Development Mode** until you need higher rate limits

---

## Next Steps

After setup is complete:

1. Test with a single post: `storyline-cli process-queue --force`
2. Monitor the first few automated posts
3. Check fallback behavior by testing with `DRY_RUN_MODE=true`
4. Enable production posting when confident
