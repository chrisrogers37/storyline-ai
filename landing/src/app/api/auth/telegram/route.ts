import { NextRequest, NextResponse } from "next/server";
import {
  verifyTelegramLogin,
  createSessionToken,
  SESSION_COOKIE,
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

  // For personal bot chats, the chat_id equals the user's Telegram ID.
  // Multi-chat selection can be added in a later phase.
  const chatId = body.id;

  const token = await createSessionToken({
    userId: body.id,
    chatId,
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

  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 86400, // 24 hours
  });

  return response;
}
