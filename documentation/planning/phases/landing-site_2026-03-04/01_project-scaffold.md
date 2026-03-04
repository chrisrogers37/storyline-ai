# Phase 01 — Project Scaffold

**Status**: ✅ COMPLETE
**Started**: 2026-03-04
**Completed**: 2026-03-04
**Effort**: Small
**Dependencies**: None

## Goal

Create a new Next.js 16 project for the Storyline AI marketing site with the standard stack (Tailwind, shadcn/ui, Drizzle/Neon), shared layout, and Vercel deployment config.

## Project Location

Create the frontend project as a new directory at the repository root:

```
landing/                          # Next.js marketing site
├── src/
│   ├── app/
│   │   ├── layout.tsx           # Root layout (fonts, metadata, analytics)
│   │   ├── page.tsx             # Landing page (Phase 02)
│   │   ├── globals.css          # Tailwind + custom styles
│   │   └── setup/               # Onboarding guide (Phase 04)
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── layout/              # Header, Footer, Container
│   │   └── landing/             # Landing page sections
│   ├── lib/
│   │   ├── db.ts                # Drizzle client (Neon serverless)
│   │   ├── schema.ts            # Drizzle schema (waitlist table)
│   │   └── utils.ts             # cn() helper, etc.
│   └── config/
│       └── site.ts              # Site metadata, nav links, social links
├── public/
│   ├── images/                  # Screenshots, mockups, icons
│   └── fonts/                   # If self-hosting fonts
├── drizzle/
│   └── migrations/              # Drizzle migration files
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── drizzle.config.ts
├── next.config.ts
├── vercel.json                  # If needed for redirects/headers
├── .env.local.example           # Template for env vars
└── .gitignore
```

## Dependencies

```json
{
  "dependencies": {
    "next": "^16",
    "react": "^19",
    "react-dom": "^19",
    "@neondatabase/serverless": "^0.10",
    "drizzle-orm": "^0.38",
    "class-variance-authority": "^0.7",
    "clsx": "^2",
    "tailwind-merge": "^2",
    "lucide-react": "^0.460",
    "@radix-ui/react-accordion": "^1",
    "@radix-ui/react-slot": "^1"
  },
  "devDependencies": {
    "typescript": "^5.7",
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "tailwindcss": "^4",
    "@tailwindcss/postcss": "^4",
    "drizzle-kit": "^0.30",
    "eslint": "^9",
    "eslint-config-next": "^16",
    "@next/eslint-plugin-next": "^16"
  }
}
```

> **Note**: Pin major versions to match the user's other projects. Use `latest` within major for initial install, then lock via lockfile.

## Environment Variables

```bash
# .env.local.example
DATABASE_URL=               # Neon connection string (same DB as Python backend)
TELEGRAM_BOT_TOKEN=         # For waitlist notification to admin
ADMIN_TELEGRAM_CHAT_ID=     # Admin's Telegram chat ID
NEXT_PUBLIC_SITE_URL=       # https://storyline.ai (or staging URL)
```

## Root Layout (`src/app/layout.tsx`)

- Set metadata: title "Storyline AI — Keep Your Stories Alive", description, OG tags
- Import Inter or Geist font (match user's other projects)
- Include Header component (logo + nav) and Footer component
- Keep nav minimal for launch: just the logo + "Join Waitlist" CTA button in header
- Footer: links to crog.gg, email (christophertrogers37@gmail.com), GitHub repo if public

## Site Config (`src/config/site.ts`)

```typescript
export const siteConfig = {
  name: "Storyline AI",
  description: "Keep your Instagram Stories alive. Automatically rotate your content library through Stories — powered by Telegram.",
  url: "https://storyline.ai",
  contact: {
    portfolio: "https://crog.gg",
    email: "christophertrogers37@gmail.com",
  },
  links: {
    github: "https://github.com/chrisrogers37/storyline-ai",
  },
}
```

## Drizzle Setup

### Schema (`src/lib/schema.ts`)

```typescript
import { pgTable, uuid, text, timestamp, boolean } from "drizzle-orm/pg-core"

export const waitlistSignups = pgTable("waitlist_signups", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: text("email").notNull().unique(),
  name: text("name"),                              // Optional
  instagramHandle: text("instagram_handle"),        // Optional, helps you prioritize
  contentCount: text("content_count"),              // Optional: "100-500", "500-1000", "1000+"
  createdAt: timestamp("created_at").defaultNow().notNull(),
  notifiedAdmin: boolean("notified_admin").default(false),
  invitedAt: timestamp("invited_at"),               // When you send them the bot link
  notes: text("notes"),                             // Your notes about this signup
})
```

### Drizzle Config (`drizzle.config.ts`)

```typescript
import { defineConfig } from "drizzle-kit"

export default defineConfig({
  schema: "./src/lib/schema.ts",
  out: "./drizzle/migrations",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
})
```

### DB Client (`src/lib/db.ts`)

```typescript
import { neon } from "@neondatabase/serverless"
import { drizzle } from "drizzle-orm/neon-http"
import * as schema from "./schema"

const sql = neon(process.env.DATABASE_URL!)
export const db = drizzle(sql, { schema })
```

## shadcn/ui Setup

Initialize shadcn/ui with:
- Style: default
- Base color: neutral or zinc (dark, modern feel)
- CSS variables: yes

Install initial components needed across phases:
- `button`, `input`, `badge`, `accordion`, `card`, `separator`

## Vercel Deployment

- Connect `landing/` directory as root in Vercel project settings
- Or use a monorepo setup with `vercel.json` at repo root pointing to `landing/`
- Set env vars: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_CHAT_ID`
- Domain: storyline.ai (or staging subdomain initially)

## Acceptance Criteria

- [ ] `npm run dev` starts without errors
- [ ] Root page renders with layout (header + footer + placeholder content)
- [ ] Drizzle can connect to Neon (`npx drizzle-kit push` succeeds)
- [ ] `waitlist_signups` table exists in Neon
- [ ] shadcn/ui components render correctly
- [ ] Deploys to Vercel successfully
- [ ] Responsive on mobile (375px) and desktop (1440px)

## Notes

- The `landing/` directory is a separate Next.js app, NOT part of the Python package. It has its own `package.json`, `node_modules`, and deployment pipeline.
- Add `landing/node_modules/` and `landing/.next/` to the root `.gitignore`.
- The Python backend and Next.js frontend share the Neon database but are otherwise independent.
