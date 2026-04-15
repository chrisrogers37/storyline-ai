/**
 * Backend (FastAPI) communication utilities.
 */

import { generateUrlToken } from "./auth";

export const BACKEND_URL =
  process.env.BACKEND_URL || "http://localhost:8000";

/**
 * GET from the FastAPI backend with URL token auth injected.
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

/**
 * GET + parse JSON, returning null on failure. Convenience for server components.
 */
export async function backendFetchJson(
  path: string,
  chatId: number,
  userId: number,
  options?: { revalidate?: number }
) {
  const res = await backendFetch(path, chatId, userId, options);
  if (!res.ok) return null;
  return res.json();
}

/**
 * POST to the FastAPI backend with URL token auth and JSON body.
 */
export async function backendPost(
  path: string,
  chatId: number,
  userId: number,
  body: Record<string, unknown> = {}
): Promise<Response> {
  const token = generateUrlToken(chatId, userId);
  return fetch(`${BACKEND_URL}/api/onboarding/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, init_data: token, chat_id: chatId }),
  });
}
