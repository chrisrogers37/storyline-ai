/**
 * POST /api/instances/:id/select — select an instance.
 *
 * Validates that the user has an active membership for the instance,
 * then reissues the JWT with activeChatId set.
 */

import { NextRequest, NextResponse } from "next/server";
import {
  verifySessionToken,
  createSessionToken,
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
  generateUrlToken,
} from "@/lib/auth";
import { BACKEND_URL } from "@/lib/backend";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  const { id } = await params;
  const instanceChatId = parseInt(id, 10);
  if (isNaN(instanceChatId)) {
    return NextResponse.json(
      { error: "Invalid instance ID" },
      { status: 400 }
    );
  }

  // Verify membership by fetching user's instances from backend
  const urlToken = generateUrlToken(0, session.userId);
  const url = `${BACKEND_URL}/api/onboarding/instances?init_data=${encodeURIComponent(urlToken)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      return NextResponse.json(
        { error: "Failed to verify membership" },
        { status: 502 }
      );
    }

    const data = await res.json();
    const instance = data.instances?.find(
      (i: { telegram_chat_id: number }) =>
        i.telegram_chat_id === instanceChatId
    );

    if (!instance) {
      return NextResponse.json(
        { error: "Not a member of this instance" },
        { status: 403 }
      );
    }

    // Reissue JWT with the selected instance
    const newToken = await createSessionToken({
      userId: session.userId,
      activeChatId: instanceChatId,
      firstName: session.firstName,
      username: session.username,
      photoUrl: session.photoUrl,
    });

    const response = NextResponse.json({
      ok: true,
      instance: {
        telegram_chat_id: instance.telegram_chat_id,
        display_name: instance.display_name,
      },
    });

    response.cookies.set(SESSION_COOKIE, newToken, SESSION_COOKIE_OPTIONS);

    return response;
  } catch (error) {
    console.error("Instance select error:", error);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
