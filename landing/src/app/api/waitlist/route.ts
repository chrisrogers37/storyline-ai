import { NextRequest, NextResponse } from "next/server"
import { getDb } from "@/lib/db"
import { waitlistSignups } from "@/lib/schema"
import { notifyAdmin } from "@/lib/telegram"
import { UTM_KEYS } from "@/lib/analytics"

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const email = body.email?.trim().toLowerCase()

    if (!email || !EMAIL_REGEX.test(email)) {
      return NextResponse.json(
        { status: "error", message: "Please enter a valid email address." },
        { status: 400 }
      )
    }

    // Capture UTM params
    const utm: Record<string, string> = {}
    for (const key of UTM_KEYS) {
      if (typeof body[key] === "string" && body[key].trim()) {
        utm[key] = body[key].trim()
      }
    }
    const notes = Object.keys(utm).length > 0 ? JSON.stringify(utm) : null

    try {
      await getDb().insert(waitlistSignups).values({ email, notes })
    } catch (err: unknown) {
      // Unique constraint violation = already registered
      if (
        err instanceof Error &&
        "code" in err &&
        (err as Record<string, unknown>).code === "23505"
      ) {
        return NextResponse.json({
          status: "success",
          message: "You're already on the list!",
          alreadyRegistered: true,
        })
      }
      throw err
    }

    // Fire-and-forget Telegram notification
    notifyAdmin(email).catch(console.error)

    return NextResponse.json({
      status: "success",
      message: "You're on the list!",
    })
  } catch {
    return NextResponse.json(
      { status: "error", message: "Something went wrong. Please try again." },
      { status: 500 }
    )
  }
}
