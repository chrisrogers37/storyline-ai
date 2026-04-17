/**
 * Telegram Login verification + URL token generation.
 *
 * Uses Node crypto — NOT Edge-safe. For session/JWT operations
 * that need to run in middleware, import from ./session.ts instead.
 */

import { createHmac, createHash } from "crypto";

export type { SessionPayload } from "./session";
export {
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
  createSessionToken,
  verifySessionToken,
  getSession,
} from "./session";

export interface TelegramLoginData {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

// 5 minutes — Telegram recommends verifying auth_date is recent to prevent replay.
// This is the login callback window, not the JWT session lifetime.
const TELEGRAM_LOGIN_TTL = 300;

// Lazy-cached derived keys (bot token doesn't change at runtime)
let _telegramLoginKey: Buffer | null = null;
let _urlTokenKey: Buffer | null = null;
let _cachedBotToken: string | null = null;

function getBotToken(): string {
  // Dev bypass — return a dummy token so backend calls gracefully return null
  if (process.env.DEV_AUTH_BYPASS === "true" && process.env.NODE_ENV !== "production") {
    return "0000000000:dev_bypass_token_for_local_review_only";
  }
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) throw new Error("TELEGRAM_BOT_TOKEN not configured");
  // Invalidate cached keys if token changes (e.g. test env)
  if (token !== _cachedBotToken) {
    _telegramLoginKey = null;
    _urlTokenKey = null;
    _cachedBotToken = token;
  }
  return token;
}

function getTelegramLoginKey(): Buffer {
  if (!_telegramLoginKey) {
    _telegramLoginKey = createHash("sha256").update(getBotToken()).digest();
  }
  return _telegramLoginKey;
}

function getUrlTokenKey(): Buffer {
  if (!_urlTokenKey) {
    _urlTokenKey = createHmac("sha256", "UrlToken")
      .update(getBotToken())
      .digest();
  }
  return _urlTokenKey;
}

/**
 * Verify data from Telegram Login Widget.
 *
 * The widget signs with SHA256(bot_token) — different from
 * WebApp initData which uses HMAC("WebAppData", bot_token).
 *
 * @see https://core.telegram.org/widgets/login#checking-authorization
 */
export function verifyTelegramLogin(data: TelegramLoginData): boolean {
  getBotToken(); // ensure token is loaded

  const now = Math.floor(Date.now() / 1000);
  if (now - data.auth_date > TELEGRAM_LOGIN_TTL) return false;

  const { hash, ...fields } = data;
  const dataCheckString = Object.entries(fields)
    .filter(([, v]) => v !== undefined && v !== null)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");

  const computedHash = createHmac("sha256", getTelegramLoginKey())
    .update(dataCheckString)
    .digest("hex");

  return computedHash === hash;
}

/**
 * Generate a signed URL token that FastAPI's validate_url_token() accepts.
 *
 * Format: {chat_id}:{user_id}:{timestamp}:{signature}
 * Secret: HMAC-SHA256("UrlToken", TELEGRAM_BOT_TOKEN)
 *
 * FastAPI enforces a 1-hour TTL on URL tokens via the embedded timestamp
 * (see src/utils/webapp_auth.py:URL_TOKEN_TTL). Tokens are not replayable
 * beyond that window.
 */
export function generateUrlToken(chatId: number, userId: number): string {
  const timestamp = Math.floor(Date.now() / 1000);
  const payload = `${chatId}:${userId}:${timestamp}`;
  const signature = createHmac("sha256", getUrlTokenKey())
    .update(payload)
    .digest("hex");
  return `${payload}:${signature}`;
}
