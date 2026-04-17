/**
 * GET /api/instances — returns the authenticated user's instance list.
 *
 * No activeChatId required (this is how the user picks one).
 * Calls the backend's DashboardService.get_user_instances().
 */

import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE, generateUrlToken } from "@/lib/auth";
import { BACKEND_URL } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  // Use chat_id=0 in the URL token — the instances endpoint only needs user_id
  const urlToken = generateUrlToken(0, session.userId);
  const url = `${BACKEND_URL}/api/onboarding/instances?init_data=${encodeURIComponent(urlToken)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error("Backend /instances error:", res.status);
      return NextResponse.json(
        { error: "Failed to fetch instances" },
        { status: res.status >= 500 ? 502 : res.status }
      );
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Instances fetch error:", error);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
