# Phase 03 — Waitlist System

**Status**: 📋 PENDING
**Effort**: Small
**Dependencies**: Phase 01 (Project Scaffold)

## Goal

Build the waitlist backend: a Next.js API route that accepts email signups, stores them in Neon, and sends you a Telegram notification instantly. No email sending infrastructure — just data capture + admin notification.

## Database

### Table: `waitlist_signups`

This table lives in the **same Neon database** as the Python backend. It's created via Drizzle migration from the Next.js project.

Schema defined in Phase 01 (`src/lib/schema.ts`):

```sql
CREATE TABLE waitlist_signups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  name TEXT,
  instagram_handle TEXT,
  content_count TEXT,                    -- "100-500", "500-1000", "1000+"
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  notified_admin BOOLEAN DEFAULT FALSE,
  invited_at TIMESTAMP,                  -- When you send them the bot link
  notes TEXT                             -- Your personal notes
);

CREATE INDEX idx_waitlist_created_at ON waitlist_signups (created_at DESC);
```

**Note on coexistence with Python backend**: The Python backend uses SQLAlchemy and raw SQL migrations in `scripts/migrations/`. The Next.js app uses Drizzle. They share the database but manage different tables. This is fine — the `waitlist_signups` table is only touched by the Next.js app. Add a comment in the Python migration folder noting this table exists but is managed by the landing site.

### Python-side awareness

Add a note file (NOT a migration) at `scripts/migrations/NOTE_waitlist_table.md`:

```markdown
# waitlist_signups table

This table is managed by the Next.js landing site (`landing/`) via Drizzle ORM.
It is NOT managed by the Python SQLAlchemy migrations.
Do not create a Python migration for this table.
```

## API Route

### `POST /api/waitlist`

**File**: `src/app/api/waitlist/route.ts`

**Request body**:
```typescript
{
  email: string       // Required, validated
}
```

**Logic**:

1. Validate email format (basic regex or use a small validator)
2. Trim and lowercase the email
3. Insert into `waitlist_signups` table
   - If duplicate (unique constraint violation), return success with `"already_registered": true`
   - Don't leak whether an email exists — always return a success-like response
4. Send Telegram notification to admin (fire-and-forget, don't block response)
5. Return success response

**Response**:
```typescript
// Success (new signup)
{ status: "success", message: "You're on the list!" }

// Success (already registered)
{ status: "success", message: "You're already on the list!", alreadyRegistered: true }

// Error (invalid email)
{ status: "error", message: "Please enter a valid email address." }

// Error (server error)
{ status: "error", message: "Something went wrong. Please try again." }
```

**Implementation**:

```typescript
// src/app/api/waitlist/route.ts
import { NextRequest, NextResponse } from "next/server"
import { db } from "@/lib/db"
import { waitlistSignups } from "@/lib/schema"
import { notifyAdmin } from "@/lib/telegram"

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const email = body.email?.trim().toLowerCase()

    if (!email || !EMAIL_REGEX.test(email)) {
      return NextResponse.json(
        { status: "error", message: "Please enter a valid email address." },
        { status: 400 }
      )
    }

    try {
      await db.insert(waitlistSignups).values({ email })
    } catch (err: any) {
      // Unique constraint violation = already registered
      if (err.code === "23505") {
        return NextResponse.json({
          status: "success",
          message: "You're already on the list!",
          alreadyRegistered: true,
        })
      }
      throw err
    }

    // Fire-and-forget Telegram notification
    notifyAdmin(email).catch(console.error)

    return NextResponse.json({
      status: "success",
      message: "You're on the list!",
    })
  } catch {
    return NextResponse.json(
      { status: "error", message: "Something went wrong. Please try again." },
      { status: 500 }
    )
  }
}
```

## Telegram Admin Notification

### `src/lib/telegram.ts`

Simple function that calls the Telegram Bot API directly — no SDK needed.

```typescript
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN!
const ADMIN_CHAT_ID = process.env.ADMIN_TELEGRAM_CHAT_ID!

export async function notifyAdmin(email: string): Promise<void> {
  const message = `🆕 New waitlist signup!\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`

  await fetch(
    `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: ADMIN_CHAT_ID,
        text: message,
        parse_mode: "HTML",
      }),
    }
  )
}
```

**Why not use the python-telegram-bot SDK?** This is a Next.js serverless function. A single HTTP call to the Bot API is simpler, faster, and has zero dependencies. The bot token is the same one used by the Python backend — it can send messages from either service.

## Rate Limiting

Basic protection against abuse. No need for Redis — use in-memory rate limiting since Vercel serverless functions are short-lived:

**Option A (simplest)**: Add a `Retry-After` header and trust Vercel's built-in DDoS protection. Good enough for launch.

**Option B (if needed later)**: Use Vercel's `@vercel/kv` or Upstash Redis for proper rate limiting. Defer unless you see abuse.

For v1, just add basic validation:
- Reject empty/malformed emails
- The unique constraint prevents duplicate inserts
- Vercel's edge network handles DDoS

## Waitlist Form Component

### `src/components/landing/waitlist-form.tsx`

Client component (`"use client"`) since it manages form state.

**States**:
```
idle → submitting → success | error | duplicate
```

**Behavior**:
- Single email input + submit button
- Client-side email validation before fetch
- Disable input + button during submission
- On success: replace form with confirmation message
- On duplicate: show friendly "already registered" message
- On error: show error message, keep form active for retry
- Store success state in localStorage to show "already registered" on return visits

**Props**:
```typescript
interface WaitlistFormProps {
  variant?: "hero" | "footer"    // Styling variants for different sections
  className?: string
}
```

**Accessibility**:
- Label on email input (visually hidden if using placeholder)
- aria-live region for status messages
- Focus management after submission

## Admin Management

You don't need a UI to manage the waitlist — just SQL queries against Neon:

```sql
-- View all signups
SELECT email, created_at, invited_at, notes
FROM waitlist_signups
ORDER BY created_at DESC;

-- Count signups
SELECT COUNT(*) FROM waitlist_signups;

-- Mark someone as invited (after you send them the bot link)
UPDATE waitlist_signups
SET invited_at = NOW(), notes = 'Sent Telegram link via email'
WHERE email = 'user@example.com';

-- Add notes
UPDATE waitlist_signups
SET notes = 'Large creator, 2k+ content pieces'
WHERE email = 'user@example.com';
```

Optionally add a CLI command to the Python backend later:
```bash
storyline-cli list-waitlist
storyline-cli invite-waitlist user@example.com
```

But that's a future enhancement — raw SQL is fine for now.

## Acceptance Criteria

- [ ] `POST /api/waitlist` with valid email returns success and creates DB row
- [ ] Duplicate email returns friendly "already registered" response (not an error)
- [ ] Invalid email returns 400 with validation message
- [ ] Telegram notification arrives in admin chat within seconds of signup
- [ ] Telegram notification failure doesn't break the signup response
- [ ] Form shows appropriate state for success, error, duplicate, and loading
- [ ] Form works on mobile (full-width, easy to tap)
- [ ] Return visitors see "already registered" state (localStorage check)

## Security Notes

- No sensitive data stored (just emails)
- No authentication needed on this endpoint (public waitlist)
- Email validation prevents injection
- Unique constraint prevents database bloat from repeated submissions
- CSRF not needed for a public form with no session
- Rate limiting can be added if abuse occurs (defer for now)
