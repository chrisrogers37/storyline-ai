import type { Metadata } from "next"
import Link from "next/link"
import { ArrowRight, Clock } from "lucide-react"
import { Checklist } from "@/components/setup/checklist"

export const metadata: Metadata = {
  title: "Getting Started — Storydump",
  robots: { index: false, follow: false },
}

const prerequisites = [
  { label: "Instagram Business or Creator account" },
  { label: "Facebook Page linked to your Instagram account" },
  { label: "Meta Developer account with an app configured" },
  { label: "Google Cloud project with Drive API enabled" },
  { label: "Google Drive folder with your media organized" },
  { label: "Telegram account (the app, not the web version)" },
]

export default function SetupOverview() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Getting Started with Storydump
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Before connecting to the Telegram bot, you&apos;ll need to set up a few
        things. Don&apos;t worry — this guide walks you through everything step
        by step.
      </p>

      <div className="mt-8 flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="h-4 w-4" />
        <span>
          Estimated time: 30-60 minutes (mostly waiting for Meta approvals)
        </span>
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-semibold">What You&apos;ll Need</h2>
        <div className="mt-4">
          <Checklist items={prerequisites} />
        </div>
      </div>

      <div className="mt-10">
        <h2 className="text-xl font-semibold">Ready? Let&apos;s go.</h2>
        <p className="mt-2 text-muted-foreground">
          Follow the guides in order. Each one builds on the last.
        </p>
        <Link
          href="/setup/instagram"
          className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Start with Instagram
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
