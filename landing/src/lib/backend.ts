/**
 * Backend (FastAPI) communication utilities.
 */

import { generateUrlToken } from "./auth";

export const BACKEND_URL =
  process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Fetch from the FastAPI backend with URL token auth injected.
 * Used by both the BFF proxy and server components.
 */
export async function backendFetch(
  path: string,
  chatId: number,
  userId: number,
  options?: { revalidate?: number }
): Promise<Response> {
  const token = generateUrlToken(chatId, userId);
  const url = `${BACKEND_URL}/api/onboarding/${path}${path.includes("?") ? "&" : "?"}init_data=${encodeURIComponent(token)}&chat_id=${chatId}`;

  return fetch(url, {
    next: options?.revalidate !== undefined ? { revalidate: options.revalidate } : undefined,
  });
}
