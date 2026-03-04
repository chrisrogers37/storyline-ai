# Phase 04 — Onboarding Guide

**Status**: 📋 PENDING
**Effort**: Medium
**Dependencies**: Phase 01 (Project Scaffold)

## Goal

Create a comprehensive, unlisted onboarding guide at `/setup` that walks accepted waitlist users through every prerequisite before they connect to the Telegram bot. This guide is NOT linked from the main navigation — you share the URL manually with each accepted user.

The guide must be extremely detailed because the prerequisites (Meta Developer setup, Instagram Business accounts, Google Cloud OAuth) are genuinely painful and poorly documented by the platforms themselves.

## URL Structure

```
/setup                        → Prerequisites overview + checklist
/setup/instagram              → Instagram Business/Creator account
/setup/meta-developer         → Meta App, Graph API permissions, App Review
/setup/google-drive           → GCP project, OAuth, Drive API
/setup/media-organize         → Folder structure, categories, naming
/setup/connect                → Telegram bot link + what to expect next
```

These pages are **server-rendered static content** — no API calls, no auth, no dynamic data. Pure MDX or TSX content pages.

## Implementation Approach

### Option A: MDX pages (recommended)

Use `@next/mdx` or `next-mdx-remote` to write guide content in Markdown with embedded components (callouts, screenshots, step indicators). This is the fastest way to write long-form instructional content.

```
src/app/setup/
├── page.tsx                    # Overview + checklist
├── layout.tsx                  # Shared setup layout (sidebar nav, progress)
├── instagram/page.mdx          # Instagram Business setup
├── meta-developer/page.mdx     # Meta Developer setup
├── google-drive/page.mdx       # Google Drive setup
├── media-organize/page.mdx     # Media organization
└── connect/page.mdx            # Telegram connection
```

### Option B: TSX pages with prose sections

If MDX setup is too heavy, use TSX pages with a `<Prose>` wrapper component for long-form text styling. Tailwind Typography plugin (`@tailwindcss/typography`) handles the formatting.

### Shared Layout

`src/app/setup/layout.tsx`:

- **Sidebar** (desktop) / **top nav** (mobile): links to each section with completion indicators
- **No progress tracking** — this isn't an interactive wizard, just documentation
- **Back to home** link at top
- **"Need help?"** link to christophertrogers37@gmail.com at bottom of every page

### Reusable Components

```
src/components/setup/
├── step-card.tsx              # Numbered step with title + description
├── callout.tsx                # Info, warning, tip callout boxes
├── screenshot.tsx             # Image with border, caption, zoom capability
├── checklist.tsx              # Interactive checkbox list (client-side only, no persistence)
├── copy-button.tsx            # Click-to-copy for URLs, IDs, etc.
└── setup-nav.tsx              # Side/top navigation between guide sections
```

---

## Page Content Specifications

### `/setup` — Overview & Checklist

**Purpose**: Give users the big picture and let them track progress.

**Content**:

```
# Getting Started with Storyline AI

Before connecting to the Telegram bot, you'll need to set up a few things.
Don't worry — this guide walks you through everything step by step.

## What You'll Need

Time estimate: 30-60 minutes (mostly waiting for Meta approvals)

### Checklist

☐ Instagram Business or Creator account
☐ Facebook Page linked to your Instagram account
☐ Meta Developer account with an app configured
☐ Google Cloud project with Drive API enabled
☐ Google Drive folder with your media organized
☐ Telegram account (the app, not the web version)

### Ready? Let's go.

Start with Instagram → [Set Up Instagram](/setup/instagram)
```

---

### `/setup/instagram` — Instagram Business Account

**Purpose**: Ensure the user has a Business or Creator account (not Personal), linked to a Facebook Page.

**Sections**:

1. **Why Business/Creator?**
   - Instagram's API only works with Business and Creator accounts
   - Personal accounts cannot be automated via the Graph API
   - Creator accounts work too — you don't need a "business"

2. **Check your current account type**
   - Step-by-step: Settings → Account → Account type
   - Screenshots showing where to find this
   - If already Business/Creator: skip to Facebook Page section

3. **Switch to Business/Creator account**
   - Settings → Account → Switch to Professional Account
   - Choose "Creator" (simpler than Business, same API access)
   - Select a category (doesn't matter much — pick "Digital Creator" or "Entrepreneur")
   - Screenshots for each step

4. **Create/link a Facebook Page**
   - Why: Meta requires a Facebook Page linked to the Instagram account for API access
   - If you don't have one: create a minimal Page (name it after your brand)
   - Step-by-step: Facebook → Create Page → fill minimal info
   - Link to Instagram: Instagram Settings → Account → Linked Accounts → Facebook
   - Screenshots showing the linking flow

5. **Verify it's working**
   - Checkpoint: "You should now see 'Professional dashboard' in your Instagram app"
   - If not: common issues and fixes

**Callouts**:
- ⚠️ "Switching to Business/Creator does NOT affect your existing followers or content"
- 💡 "Creator accounts get the same API access as Business — pick whichever you prefer"
- ⚠️ "You MUST have a Facebook Page linked, even if you never use Facebook"

---

### `/setup/meta-developer` — Meta Developer App Setup

**Purpose**: Walk through the most painful part — creating a Meta App with the right permissions for Instagram Story publishing.

**This is the longest and most detailed page.** Meta's developer portal changes frequently and their docs are notoriously confusing.

**Sections**:

1. **Create a Meta Developer account**
   - Go to developers.facebook.com
   - Log in with your Facebook account (must be the one linked to the Instagram account)
   - Accept developer terms
   - Screenshots of the registration flow

2. **Create a new App**
   - My Apps → Create App
   - App type: **"Business"** (not Consumer, not None)
   - App name: anything (e.g., "Storyline AI" or "My Story Bot")
   - App contact email: your email
   - Business portfolio: create one or use existing
   - Screenshots for each step

3. **Add Instagram Graph API product**
   - App Dashboard → Add Product → Instagram Graph API → Set Up
   - This enables Instagram API endpoints for your app
   - Screenshot showing where to find this

4. **Configure Instagram Basic Display** (if needed)
   - Some flows require Basic Display API as well
   - Add Product → Instagram Basic Display → Set Up
   - Screenshot of configuration

5. **Generate an access token**
   - Two paths depending on whether Storyline handles OAuth or user generates manually:
     - **Path A (Storyline OAuth)**: You'll connect your account during Storyline setup — the app just needs the right permissions
     - **Path B (Manual token)**: Graph API Explorer → select your app → generate token
   - Explain which scopes are needed:
     - `instagram_basic` — read account info
     - `instagram_content_publish` — post Stories
     - `pages_show_list` — list connected Pages
     - `pages_read_engagement` — read Page info
   - Screenshots of the token generation flow

6. **App Review (the hard part)**
   - ⚠️ "This is the most time-consuming step. Meta reviews your app before granting publishing permissions. This can take 1-5 business days."
   - What you need to submit:
     - Screencast showing how your app uses the Instagram API
     - Description of your use case
     - Privacy policy URL (can be a simple page on your site)
   - How to submit for review: App Review → Permissions and Features → Request `instagram_content_publish`
   - Tips for faster approval:
     - Keep the screencast short (< 2 minutes)
     - Show the exact user flow (upload → schedule → publish)
     - Mention that content is user-owned and approved before posting
   - What to do while waiting: "You can proceed with Google Drive setup and media organization while waiting for Meta approval"

7. **Get your App credentials**
   - App Dashboard → Settings → Basic
   - Copy: **App ID** and **App Secret**
   - ⚠️ "Never share your App Secret publicly"
   - You'll enter these during Storyline's Telegram setup

8. **Common issues**
   - "My app is in Development mode" → That's fine for personal use with up to 5 test users
   - "I don't see instagram_content_publish" → Make sure your app type is Business
   - "App Review was rejected" → Common reasons and how to resubmit
   - "Token expires after 60 days" → Storyline handles auto-refresh, but explain the concept

**Callouts**:
- ⚠️ "Meta's developer portal changes frequently. If a screenshot doesn't match exactly, look for similar options nearby."
- 💡 "If you only plan to use Storyline for your own account(s), Development Mode is sufficient — you don't strictly need App Review. But it's recommended for stability."
- ⚠️ "The App Secret is like a password. Never post it publicly or commit it to Git."

---

### `/setup/google-drive` — Google Cloud & Drive Setup

**Purpose**: Create a Google Cloud project with Drive API enabled and OAuth credentials.

**Sections**:

1. **Create a Google Cloud project**
   - Go to console.cloud.google.com
   - Create new project (name: "Storyline AI" or similar)
   - Screenshots

2. **Enable Google Drive API**
   - APIs & Services → Library → search "Google Drive API" → Enable
   - Screenshot

3. **Configure OAuth consent screen**
   - APIs & Services → OAuth consent screen
   - User type: **External** (even for personal use)
   - Fill in: App name, support email, developer email
   - Scopes: add `drive.readonly`
   - Test users: **add your own Google email address**
   - ⚠️ "While in testing mode, only emails listed as test users can authorize. Add yourself!"
   - Screenshots for each step

4. **Create OAuth credentials**
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Web application**
   - Authorized redirect URIs: add `https://storyline-ai-production.up.railway.app/auth/google-drive/callback` (or whatever the current callback URL is)
   - Copy: **Client ID** and **Client Secret**
   - Screenshots

5. **Verify it's working**
   - Checkpoint: "You should now have a Client ID and Client Secret. You'll enter these during Storyline's Telegram setup."

**Callouts**:
- 💡 "Google's free tier is more than enough — Drive API has a generous quota for personal use"
- ⚠️ "Make sure to add yourself as a test user in the OAuth consent screen, or authorization will fail"
- ⚠️ "The redirect URI must match EXACTLY — including https:// and no trailing slash"

---

### `/setup/media-organize` — Organizing Your Media

**Purpose**: Help users structure their Google Drive folder for optimal Storyline performance.

**Sections**:

1. **Folder structure = categories**
   - Storyline treats each subfolder as a category
   - Show recommended structure:
   ```
   My Instagram Stories/          ← this is the root folder
   ├── memes/                     ← category: "memes"
   │   ├── funny-cat.jpg
   │   ├── monday-mood.png
   │   └── ...
   ├── products/                  ← category: "products"
   │   ├── new-tshirt.jpg
   │   ├── sale-banner.png
   │   └── ...
   ├── behind-the-scenes/         ← category: "behind-the-scenes"
   │   ├── studio-shot.jpg
   │   └── ...
   └── announcements/             ← category: "announcements"
       ├── holiday-hours.png
       └── ...
   ```

2. **Image requirements**
   - Aspect ratio: 9:16 (1080x1920 ideal)
   - Formats: JPG, PNG, GIF
   - Max size: 100MB per file
   - Storyline auto-validates and skips incompatible files
   - 💡 "Don't worry about perfection — Storyline will tell you which files need attention"

3. **Category mixing**
   - Explain how Storyline distributes posts across categories
   - Example: 70% memes, 20% products, 10% announcements
   - "You can adjust these ratios anytime from Telegram"

4. **How many files do you need?**
   - Minimum: ~30 files for a week of posting (3/day × 7 days + buffer)
   - Ideal: 100+ for good variety
   - "Storyline tracks what's been posted and cycles through your library evenly"

5. **Tips**
   - Keep filenames descriptive (helps when reviewing in Telegram)
   - Remove content you'd never want to post (Storyline will try to post everything)
   - You can add/remove files anytime — Storyline syncs automatically

---

### `/setup/connect` — Connect to Telegram

**Purpose**: The final step — link them to the Telegram bot.

**Sections**:

1. **Install Telegram** (if needed)
   - Download links for iOS, Android, Desktop
   - "Already have Telegram? Skip to step 2"

2. **Start the bot**
   - Provide the `t.me/YourBotName` link (this link is ONLY shared on this unlisted page and in your personal emails to waitlist acceptees)
   - "Tap the link above → Open in Telegram → Tap 'Start'"
   - Screenshot of the /start flow

3. **Complete the setup wizard**
   - "The bot will walk you through connecting your Instagram and Google Drive"
   - "Have your Meta App credentials and Google OAuth credentials ready"
   - Brief overview of what each wizard step does (connects back to the guides above)

4. **What happens next**
   - "Once setup is complete, Storyline will:"
     - Sync your Google Drive media
     - Create your first 7-day schedule
     - Start sending Story previews to your Telegram chat
   - "Approve, skip, or auto-post — it's all up to you"

5. **Getting help**
   - "Hit a snag? Reach out at christophertrogers37@gmail.com"
   - "Or message me at [crog.gg](https://crog.gg)"

---

## Design Notes

- **Tone**: Friendly, patient, thorough. Assume the user has never used a developer console before. Over-explain rather than under-explain.
- **Screenshots**: Use placeholder boxes with captions during development. Real screenshots added before sharing with users.
- **Code/values to copy**: Use the `<CopyButton>` component for anything the user needs to paste (URLs, IDs, etc.)
- **Checklist persistence**: The overview checklist can use localStorage to persist checks across visits. Nice-to-have, not required for v1.
- **Print-friendly**: Consider adding `@media print` styles — some users will want to print the Meta section.

## Acceptance Criteria

- [ ] All 6 pages render correctly with proper navigation between them
- [ ] Setup sidebar/nav shows all sections with working links
- [ ] Each page has clear numbered steps
- [ ] Callout components render correctly (info, warning, tip styles)
- [ ] Copy button works for URLs and credentials
- [ ] Pages are NOT linked from the main landing page navigation
- [ ] Pages ARE accessible via direct URL (`/setup`, `/setup/meta-developer`, etc.)
- [ ] Responsive layout works on mobile (users may follow the guide on their phone while setting up on desktop)
- [ ] "Need help?" contact link appears on every page
- [ ] Back to overview / next section navigation works
