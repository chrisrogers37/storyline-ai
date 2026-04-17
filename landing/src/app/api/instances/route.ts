/**
 * GET /api/instances — returns the authenticated user's instance list.
 *
 * No activeChatId required (this is how the user picks one).
 * Calls the backend's DashboardService.get_user_instances().
 */

import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE } from "@/lib/auth";
import { fetchUserInstances } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  try {
    const instances = await fetchUserInstances(session.userId);
    if (instances === null) {
      return NextResponse.json(
        { error: "Failed to fetch instances" },
        { status: 502 }
      );
    }
    return NextResponse.json({ instances });
  } catch (error) {
    console.error("Instances fetch error:", error);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
