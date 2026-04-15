import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { StepCard } from "@/components/setup/step-card"
import { Callout } from "@/components/setup/callout"
import { Screenshot } from "@/components/setup/screenshot"
import { CopyButton } from "@/components/setup/copy-button"

export const metadata: Metadata = {
  title: "Meta Developer Setup — Storyline AI",
  robots: { index: false, follow: false },
}

export default function MetaDeveloperSetup() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Meta Developer App Setup
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        This is the most involved step. You&apos;ll create a Meta App with the
        right permissions for Instagram Story publishing. Meta&apos;s developer
        portal can be confusing — follow each step carefully.
      </p>
      <Callout type="warning" className="mt-4">
        Meta&apos;s developer portal changes frequently. If a screenshot
        doesn&apos;t match exactly, look for similar options nearby.
      </Callout>

      <div className="mt-10 space-y-10">
        <StepCard number={1} title="Create a Meta Developer account">
          <p>
            Go to{" "}
            <CopyButton value="https://developers.facebook.com" /> and
            log in with the Facebook account linked to your Instagram.
          </p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>Click &quot;Get Started&quot; or &quot;Register&quot;</li>
            <li>Accept the developer terms</li>
            <li>Verify your account if prompted</li>
          </ol>
          <Screenshot caption="Meta Developer registration page" />
        </StepCard>

        <StepCard number={2} title="Create a new App">
          <ol className="list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                My Apps &rarr; Create App
              </span>
            </li>
            <li>
              App type:{" "}
              <span className="font-medium text-foreground">Business</span> (not
              Consumer, not None)
            </li>
            <li>
              App name: anything you like (e.g., &quot;Storyline AI&quot; or
              &quot;My Story Bot&quot;)
            </li>
            <li>App contact email: your email address</li>
            <li>Business portfolio: create one or use an existing one</li>
          </ol>
          <Screenshot caption="Create App dialog with Business type selected" />
        </StepCard>

        <StepCard number={3} title="Add Instagram Graph API product">
          <p>From your App Dashboard:</p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Click{" "}
              <span className="font-medium text-foreground">Add Product</span>{" "}
              in the sidebar
            </li>
            <li>
              Find{" "}
              <span className="font-medium text-foreground">
                Instagram Graph API
              </span>
            </li>
            <li>
              Click{" "}
              <span className="font-medium text-foreground">Set Up</span>
            </li>
          </ol>
          <Screenshot caption="Add Product — Instagram Graph API" />
        </StepCard>

        <StepCard number={4} title="Configure Instagram Basic Display (if needed)">
          <p>
            Some flows also require the Basic Display API. Add it the same way:
          </p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              <span className="font-medium text-foreground">
                Add Product &rarr; Instagram Basic Display &rarr; Set Up
              </span>
            </li>
          </ol>
          <Screenshot caption="Instagram Basic Display setup" />
        </StepCard>

        <StepCard number={5} title="Generate an access token">
          <p>
            Storyline handles OAuth for you during the Telegram setup wizard, so
            your app just needs the right permissions configured. The required
            scopes are:
          </p>
          <ul className="mt-2 space-y-1">
            <li>
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                instagram_basic
              </code>{" "}
              — read account info
            </li>
            <li>
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                instagram_content_publish
              </code>{" "}
              — post Stories
            </li>
            <li>
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                pages_show_list
              </code>{" "}
              — list connected Pages
            </li>
            <li>
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                pages_read_engagement
              </code>{" "}
              — read Page info
            </li>
          </ul>
          <Screenshot caption="Graph API Explorer with required scopes" />
        </StepCard>

        <StepCard number={6} title="App Review (the hard part)">
          <Callout type="warning" className="mb-3">
            This is the most time-consuming step. Meta reviews your app before
            granting publishing permissions. This can take 1-5 business days.
          </Callout>
          <p>To submit for review:</p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                App Review &rarr; Permissions and Features
              </span>
            </li>
            <li>
              Request{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                instagram_content_publish
              </code>
            </li>
            <li>
              Prepare a short screencast (&lt; 2 minutes) showing how your app
              uses the Instagram API
            </li>
            <li>Write a description of your use case</li>
            <li>
              Provide a privacy policy URL (a simple page on your site works)
            </li>
          </ol>
          <p className="mt-3 font-medium text-foreground">
            Tips for faster approval:
          </p>
          <ul className="mt-1 list-inside list-disc space-y-1">
            <li>Keep the screencast short and focused</li>
            <li>
              Show the exact flow: content selection &rarr; scheduling &rarr;
              publishing
            </li>
            <li>
              Emphasize that content is user-owned and approved before posting
            </li>
          </ul>
          <Callout type="tip" className="mt-3">
            If you only plan to use Storyline for your own account(s),
            Development Mode is sufficient — you don&apos;t strictly need App
            Review. But it&apos;s recommended for stability.
          </Callout>
          <p className="mt-3">
            While waiting for approval, you can proceed with{" "}
            <Link
              href="/setup/google-drive"
              className="underline underline-offset-4 hover:text-foreground"
            >
              Google Drive setup
            </Link>{" "}
            and{" "}
            <Link
              href="/setup/media-organize"
              className="underline underline-offset-4 hover:text-foreground"
            >
              media organization
            </Link>
            .
          </p>
        </StepCard>

        <StepCard number={7} title="Get your App credentials">
          <p>From your App Dashboard:</p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                Settings &rarr; Basic
              </span>
            </li>
            <li>
              Copy your{" "}
              <span className="font-medium text-foreground">App ID</span> and{" "}
              <span className="font-medium text-foreground">App Secret</span>
            </li>
            <li>
              You&apos;ll enter these during Storyline&apos;s Telegram setup
            </li>
          </ol>
          <Screenshot caption="App Settings showing App ID and App Secret" />
          <Callout type="warning" className="mt-3">
            The App Secret is like a password. Never share it publicly or commit
            it to Git.
          </Callout>
        </StepCard>

        <StepCard number={8} title="Common issues">
          <div className="space-y-3">
            <div>
              <p className="font-medium text-foreground">
                &quot;My app is in Development mode&quot;
              </p>
              <p>
                That&apos;s fine for personal use with up to 5 test users. Add
                your Instagram account as a test user in the App Dashboard.
              </p>
            </div>
            <div>
              <p className="font-medium text-foreground">
                &quot;I don&apos;t see instagram_content_publish&quot;
              </p>
              <p>
                Make sure your app type is set to Business. Consumer and None app
                types don&apos;t have access to publishing permissions.
              </p>
            </div>
            <div>
              <p className="font-medium text-foreground">
                &quot;App Review was rejected&quot;
              </p>
              <p>
                Review the rejection reason carefully. Common issues include
                incomplete screencasts, missing privacy policy, or unclear use
                case descriptions. You can resubmit after addressing the
                feedback.
              </p>
            </div>
            <div>
              <p className="font-medium text-foreground">
                &quot;Token expires after 60 days&quot;
              </p>
              <p>
                Storyline handles token auto-refresh automatically. You
                don&apos;t need to manually renew tokens.
              </p>
            </div>
          </div>
        </StepCard>
      </div>

      <div className="mt-12 flex items-center justify-between">
        <Link
          href="/setup/instagram"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Instagram Account
        </Link>
        <Link
          href="/setup/google-drive"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Next: Google Drive
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
