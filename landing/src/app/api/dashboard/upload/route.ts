/**
 * Dedicated upload proxy — forwards multipart file uploads to FastAPI.
 *
 * Separated from the generic BFF proxy because file uploads require
 * streaming the raw body (not JSON re-encoding).
 */

import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE } from "@/lib/auth";
import { generateUrlToken } from "@/lib/auth";
import { BACKEND_URL } from "@/lib/backend";

export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  const urlToken = generateUrlToken(session.chatId, session.userId);
  const url = new URL("/api/onboarding/upload-media", BACKEND_URL);
  url.searchParams.set("init_data", urlToken);
  url.searchParams.set("chat_id", String(session.chatId));

  // Forward the raw multipart body to FastAPI
  const contentType = request.headers.get("content-type") || "";
  const body = await request.arrayBuffer();

  try {
    const backendResponse = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": contentType },
      body: body,
    });

    if (backendResponse.status >= 500) {
      console.error("Upload backend 5xx:", backendResponse.status);
      return NextResponse.json(
        { error: "Backend unavailable" },
        { status: 502 }
      );
    }

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    console.error("Upload proxy error:", error);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
