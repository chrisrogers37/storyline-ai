/**
 * BFF Proxy — forwards /api/dashboard/* requests to FastAPI backend.
 *
 * Auth flow:
 *  1. Verify JWT session cookie -> extract chatId + userId
 *  2. Generate a signed URL token (same format FastAPI expects)
 *  3. Forward the request to FastAPI's /api/onboarding/* endpoints
 */

import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE } from "@/lib/auth";
import { generateUrlToken } from "@/lib/auth";
import { BACKEND_URL } from "@/lib/backend";

// Allowlisted backend path prefixes the proxy can forward to.
// Prevents path traversal to arbitrary FastAPI endpoints.
const ALLOWED_PATHS = [
  "analytics",
  "accounts",
  "history-detail",
  "media-stats",
  "queue-detail",
  "queue-preview",
  "system-status",
  "toggle-setting",
  "update-setting",
  "switch-account",
  "sync-media",
  "oauth-url",
  "init",
  "schedule",
  "complete",
  "media-folder",
  "start-indexing",
  "add-account",
  "remove-account",
  "disconnect-gdrive",
];

async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  const { path } = await params;
  const backendPath = path.join("/");

  // Validate path against allowlist
  const topSegment = path[0];
  if (!topSegment || !ALLOWED_PATHS.includes(topSegment)) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  const url = new URL(`/api/onboarding/${backendPath}`, BACKEND_URL);

  // Belt-and-suspenders: verify resolved URL stays within /api/onboarding/
  if (!url.pathname.startsWith("/api/onboarding/")) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  // Forward query params and inject auth
  const searchParams = new URL(request.url).searchParams;
  searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const urlToken = generateUrlToken(session.chatId, session.userId);
  url.searchParams.set("init_data", urlToken);
  url.searchParams.set("chat_id", String(session.chatId));

  const fetchOptions: RequestInit = {
    method: request.method,
  };

  // Only set Content-Type and body for methods that have a body
  if (request.method !== "GET" && request.method !== "HEAD") {
    let body: Record<string, unknown> = {};
    try {
      body = await request.json();
    } catch {
      // No JSON body — still inject auth fields
    }
    fetchOptions.headers = { "Content-Type": "application/json" };
    fetchOptions.body = JSON.stringify({
      ...body,
      init_data: urlToken,
      chat_id: session.chatId,
    });
  }

  try {
    const backendResponse = await fetch(url.toString(), fetchOptions);

    // Don't leak backend 5xx details to the client
    if (backendResponse.status >= 500) {
      console.error("Backend 5xx:", backendResponse.status, url.pathname);
      return NextResponse.json(
        { error: "Backend unavailable" },
        { status: 502 }
      );
    }

    const contentType = backendResponse.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await backendResponse.json();
      return NextResponse.json(data, { status: backendResponse.status });
    }

    const text = await backendResponse.text();
    return new NextResponse(text, {
      status: backendResponse.status,
      headers: { "Content-Type": contentType },
    });
  } catch (error) {
    console.error("BFF proxy error:", error);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
