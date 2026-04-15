/**
 * Client-side API helpers for dashboard components.
 * All calls go through the BFF proxy which handles auth injection.
 */

export async function postApi(path: string, body: Record<string, unknown> = {}) {
  const res = await fetch(`/api/dashboard/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Request failed" }));
    throw new Error(err.error || `API error ${res.status}`);
  }
  return res.json();
}

export async function getApi(path: string) {
  const res = await fetch(`/api/dashboard/${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Request failed" }));
    throw new Error(err.error || `API error ${res.status}`);
  }
  return res.json();
}
