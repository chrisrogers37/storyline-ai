import { NextRequest, NextResponse } from "next/server";
import {
  verifyTelegramLogin,
  createSessionToken,
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
  type TelegramLoginData,
} from "@/lib/auth";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as TelegramLoginData;

  // Validate required fields
  if (!body.id || !body.first_name || !body.auth_date || !body.hash) {
    return NextResponse.json(
      { error: "Missing required Telegram login fields" },
      { status: 400 }
    );
  }

  // Verify Telegram signature
  if (!verifyTelegramLogin(body)) {
    return NextResponse.json(
      { error: "Invalid Telegram login signature" },
      { status: 401 }
    );
  }

  // Multi-account: start with no instance selected. The user picks one
  // on the /instances page, which reissues the JWT with activeChatId set.
  const token = await createSessionToken({
    userId: body.id,
    activeChatId: null,
    firstName: body.first_name,
    username: body.username,
    photoUrl: body.photo_url,
  });

  const response = NextResponse.json({
    ok: true,
    user: {
      id: body.id,
      firstName: body.first_name,
      lastName: body.last_name,
      username: body.username,
      photoUrl: body.photo_url,
    },
  });

  response.cookies.set(SESSION_COOKIE, token, SESSION_COOKIE_OPTIONS);

  return response;
}
