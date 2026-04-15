import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { StepCard } from "@/components/setup/step-card"
import { Callout } from "@/components/setup/callout"
import { Screenshot } from "@/components/setup/screenshot"
import { CopyButton } from "@/components/setup/copy-button"

export const metadata: Metadata = {
  title: "Google Drive Setup — Storyline AI",
  robots: { index: false, follow: false },
}

export default function GoogleDriveSetup() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Google Cloud &amp; Drive Setup
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Create a Google Cloud project with the Drive API enabled and OAuth
        credentials so Storyline can read your media files.
      </p>

      <div className="mt-10 space-y-10">
        <StepCard number={1} title="Create a Google Cloud project">
          <ol className="list-inside list-decimal space-y-1">
            <li>
              Go to <CopyButton value="https://console.cloud.google.com" />
            </li>
            <li>
              Click{" "}
              <span className="font-medium text-foreground">
                Select a project &rarr; New Project
              </span>
            </li>
            <li>
              Name it something recognizable (e.g., &quot;Storyline AI&quot;)
            </li>
            <li>Click Create</li>
          </ol>
          <Screenshot caption="Google Cloud — Create new project" />
          <Callout type="tip" className="mt-3">
            Google&apos;s free tier is more than enough — the Drive API has a
            generous quota for personal use.
          </Callout>
        </StepCard>

        <StepCard number={2} title="Enable Google Drive API">
          <ol className="list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                APIs &amp; Services &rarr; Library
              </span>
            </li>
            <li>Search for &quot;Google Drive API&quot;</li>
            <li>
              Click{" "}
              <span className="font-medium text-foreground">Enable</span>
            </li>
          </ol>
          <Screenshot caption="Enabling Google Drive API in the library" />
        </StepCard>

        <StepCard number={3} title="Configure OAuth consent screen">
          <ol className="list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                APIs &amp; Services &rarr; OAuth consent screen
              </span>
            </li>
            <li>
              User type:{" "}
              <span className="font-medium text-foreground">External</span>{" "}
              (even for personal use)
            </li>
            <li>
              Fill in: App name, user support email, developer contact email
            </li>
            <li>
              Add scope:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                drive.readonly
              </code>
            </li>
            <li>
              Under Test users:{" "}
              <span className="font-medium text-foreground">
                add your own Google email address
              </span>
            </li>
          </ol>
          <Screenshot caption="OAuth consent screen configuration" />
          <Callout type="warning" className="mt-3">
            While in testing mode, only emails listed as test users can
            authorize. Make sure to add yourself, or authorization will fail.
          </Callout>
        </StepCard>

        <StepCard number={4} title="Create OAuth credentials">
          <ol className="list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                APIs &amp; Services &rarr; Credentials &rarr; Create Credentials
                &rarr; OAuth client ID
              </span>
            </li>
            <li>
              Application type:{" "}
              <span className="font-medium text-foreground">
                Web application
              </span>
            </li>
            <li>Add an authorized redirect URI:</li>
          </ol>
          <div className="mt-2">
            <CopyButton value="https://storyline-ai-production.up.railway.app/auth/google-drive/callback" />
          </div>
          <ol className="mt-2 list-inside list-decimal space-y-1" start={4}>
            <li>Click Create</li>
            <li>
              Copy the{" "}
              <span className="font-medium text-foreground">Client ID</span> and{" "}
              <span className="font-medium text-foreground">Client Secret</span>
            </li>
          </ol>
          <Screenshot caption="OAuth client ID creation with redirect URI" />
          <Callout type="warning" className="mt-3">
            The redirect URI must match EXACTLY — including{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
              https://
            </code>{" "}
            and no trailing slash.
          </Callout>
        </StepCard>

        <StepCard number={5} title="Verify it's working">
          <p>
            You should now have two values ready for the Storyline setup wizard:
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1">
            <li>
              <span className="font-medium text-foreground">Client ID</span> — a
              long string ending in{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                .apps.googleusercontent.com
              </code>
            </li>
            <li>
              <span className="font-medium text-foreground">Client Secret</span>{" "}
              — a shorter alphanumeric string
            </li>
          </ul>
          <p className="mt-2">
            Keep these handy — you&apos;ll enter them during the Telegram bot
            setup.
          </p>
        </StepCard>
      </div>

      <div className="mt-12 flex items-center justify-between">
        <Link
          href="/setup/meta-developer"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Meta Developer
        </Link>
        <Link
          href="/setup/media-organize"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Next: Organize Media
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
