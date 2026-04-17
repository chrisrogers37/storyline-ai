/**
 * Session management — Edge Runtime compatible.
 *
 * This module contains only jose + Next.js imports (no Node crypto),
 * so it can be safely imported from middleware (Edge Runtime).
 */

import { SignJWT, jwtVerify } from "jose";
import { cache } from "react";
import { cookies } from "next/headers";

export interface SessionPayload {
  userId: number;
  activeChatId: number | null;
  firstName: string;
  username?: string;
  photoUrl?: string;
}

export const SESSION_COOKIE = "storyline_session";

const JWT_EXPIRY = "24h";
const JWT_MAX_AGE_SECONDS = 86400; // must match JWT_EXPIRY

/** Shared cookie options for the session JWT. */
export const SESSION_COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: JWT_MAX_AGE_SECONDS,
};

// Lazy-initialized: Next.js evaluates modules at build time during page data
// collection, but env vars aren't available then. Validate on first use.
let _jwtSecret: Uint8Array | null = null;

function getJwtSecret(): Uint8Array {
  if (!_jwtSecret) {
    const raw = process.env.JWT_SECRET;
    if (!raw || raw.length < 32) {
      throw new Error(
        "JWT_SECRET must be set to a random 32+ character string"
      );
    }
    _jwtSecret = new TextEncoder().encode(raw);
  }
  return _jwtSecret;
}

export async function createSessionToken(
  payload: SessionPayload
): Promise<string> {
  return new SignJWT({
    userId: payload.userId,
    activeChatId: payload.activeChatId,
    firstName: payload.firstName,
    username: payload.username,
    photoUrl: payload.photoUrl,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(JWT_EXPIRY)
    .sign(getJwtSecret());
}

export async function verifySessionToken(
  token: string
): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getJwtSecret());
    return {
      userId: payload.userId as number,
      activeChatId: (payload.activeChatId as number) ?? null,
      firstName: payload.firstName as string,
      username: payload.username as string | undefined,
      photoUrl: payload.photoUrl as string | undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Get the current session from cookies, deduped per request via React cache().
 * Returns null if no valid session — callers decide whether to redirect.
 */
export const getSession = cache(async (): Promise<SessionPayload | null> => {
  // Dev auth bypass — returns a mock session without cookie validation.
  if (process.env.DEV_AUTH_BYPASS === "true" && process.env.NODE_ENV !== "production") {
    // Use userId as activeChatId so dashboard pages can generate valid backend tokens
    return { userId: 0, activeChatId: 0, firstName: "Dev User", username: "dev" };
  }
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  return verifySessionToken(token);
});
