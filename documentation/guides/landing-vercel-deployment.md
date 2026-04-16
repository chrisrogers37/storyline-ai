# Landing Site — Vercel Deployment

The Next.js landing/dashboard app lives in `landing/` and deploys to Vercel.

## Required Environment Variables

Set these in **Vercel → Project Settings → Environment Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `DATABASE_URL` | Server | Neon PostgreSQL connection string (same DB as Python backend) |
| `TELEGRAM_BOT_TOKEN` | Server | Telegram bot token — used for auth verification and waitlist notifications |
| `ADMIN_TELEGRAM_CHAT_ID` | Server | Chat ID to receive waitlist signup notifications |
| `JWT_SECRET` | Server | Random 32+ character string for signing session tokens |
| `BACKEND_URL` | Server | FastAPI backend URL (e.g. `https://storyline-api.up.railway.app`) |
| `NEXT_PUBLIC_SITE_URL` | Client | Public site URL (e.g. `https://storyline.ai`) |
| `NEXT_PUBLIC_TELEGRAM_BOT_NAME` | Client | Bot username without `@` (e.g. `storyline_ai_bot`) — required for the Telegram Login Widget on `/login` |

### Client vs Server Variables

- **`NEXT_PUBLIC_*`** variables are inlined at build time and visible in the browser bundle. They must be set before the build runs.
- **Server** variables are only available in API routes, middleware, and server components. They can be changed without rebuilding.

### Common Issues

- **Login page shows "Telegram login is not configured"**: `NEXT_PUBLIC_TELEGRAM_BOT_NAME` is missing. Add it in Vercel env vars and redeploy (client vars require a rebuild).
- **Login widget loads but auth fails**: `TELEGRAM_BOT_TOKEN` is missing or doesn't match the bot named in `NEXT_PUBLIC_TELEGRAM_BOT_NAME`.
- **Dashboard API calls fail**: `BACKEND_URL` is missing or the Railway backend is down.

## Vercel Project Settings

- **Root Directory**: `landing`
- **Framework Preset**: Next.js
- **Build Command**: `next build` (default)
- **Node.js Version**: 20.x
