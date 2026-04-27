import { ImageResponse } from "next/og"

export const runtime = "edge"

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#09090b",
          color: "#fafafa",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "24px",
          }}
        >
          <div
            style={{
              fontSize: "72px",
              fontWeight: 700,
              letterSpacing: "-0.02em",
            }}
          >
            Storyline AI
          </div>
          <div
            style={{
              fontSize: "32px",
              color: "#a1a1aa",
              maxWidth: "800px",
              textAlign: "center",
            }}
          >
            Instagram Stories on Autopilot
          </div>
          <div
            style={{
              display: "flex",
              gap: "32px",
              marginTop: "16px",
              fontSize: "20px",
              color: "#71717a",
            }}
          >
            <span>Google Drive</span>
            <span>→</span>
            <span>Telegram Approval</span>
            <span>→</span>
            <span>Auto-Posted</span>
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    }
  )
}
