const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN
const ADMIN_CHAT_ID = process.env.ADMIN_TELEGRAM_CHAT_ID

export async function notifyAdmin(email: string): Promise<void> {
  if (!BOT_TOKEN || !ADMIN_CHAT_ID) {
    console.warn(
      "Telegram notification skipped: missing BOT_TOKEN or ADMIN_CHAT_ID"
    )
    return
  }

  const message = `New waitlist signup!\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`

  await fetch(
    `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: ADMIN_CHAT_ID,
        text: message,
      }),
    }
  )
}
