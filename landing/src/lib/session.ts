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
  chatId: number;
  firstName: string;
  username?: string;
  photoUrl?: string;
}

export const SESSION_COOKIE = "storyline_session";

const JWT_EXPIRY = "24h";

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
    chatId: payload.chatId,
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
      chatId: payload.chatId as number,
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
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  return verifySessionToken(token);
});
