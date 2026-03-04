import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { StepCard } from "@/components/setup/step-card"
import { Callout } from "@/components/setup/callout"
import { Screenshot } from "@/components/setup/screenshot"

export const metadata: Metadata = {
  title: "Instagram Account Setup — Storyline AI",
  robots: { index: false, follow: false },
}

export default function InstagramSetup() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Instagram Business Account
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Instagram&apos;s API only works with Business or Creator accounts. This
        guide ensures your account is set up correctly and linked to a Facebook
        Page.
      </p>

      <div className="mt-10 space-y-10">
        <StepCard number={1} title="Why Business or Creator?">
          <p>
            Instagram&apos;s Graph API requires a Professional account — either
            Business or Creator. Personal accounts cannot be automated.
          </p>
          <Callout type="tip" className="mt-3">
            Creator accounts get the same API access as Business accounts. Pick
            whichever feels right — &quot;Digital Creator&quot; or
            &quot;Entrepreneur&quot; both work.
          </Callout>
        </StepCard>

        <StepCard number={2} title="Check your current account type">
          <p>Open the Instagram app and navigate to:</p>
          <p className="mt-2 font-medium text-foreground">
            Settings &rarr; Account &rarr; Account type
          </p>
          <Screenshot caption="Instagram Settings showing account type" />
          <p>
            If you already see &quot;Business&quot; or &quot;Creator,&quot; skip
            to Step 4 (Facebook Page).
          </p>
        </StepCard>

        <StepCard number={3} title="Switch to a Professional account">
          <p>If you&apos;re on a Personal account, switch now:</p>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                Settings &rarr; Account &rarr; Switch to Professional Account
              </span>
            </li>
            <li>
              Choose <span className="font-medium text-foreground">Creator</span>
            </li>
            <li>
              Select a category — &quot;Digital Creator&quot; or
              &quot;Entrepreneur&quot; works fine
            </li>
            <li>Complete the remaining prompts</li>
          </ol>
          <Screenshot caption="Switch to Professional Account flow" />
          <Callout type="warning" className="mt-3">
            Switching to Business or Creator does NOT affect your existing
            followers, posts, or content. It only unlocks professional tools and
            API access.
          </Callout>
        </StepCard>

        <StepCard number={4} title="Create and link a Facebook Page">
          <p>
            Meta requires a Facebook Page linked to your Instagram account for
            API access — even if you never use Facebook.
          </p>

          <h4 className="mt-4 font-medium text-foreground">
            If you don&apos;t have a Facebook Page:
          </h4>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Go to{" "}
              <span className="font-medium text-foreground">
                facebook.com &rarr; Create Page
              </span>
            </li>
            <li>Name it after your brand or Instagram handle</li>
            <li>Fill in the minimum required info and publish</li>
          </ol>

          <h4 className="mt-4 font-medium text-foreground">
            Link the Page to Instagram:
          </h4>
          <ol className="mt-2 list-inside list-decimal space-y-1">
            <li>
              Open Instagram &rarr;{" "}
              <span className="font-medium text-foreground">
                Settings &rarr; Account &rarr; Linked Accounts &rarr; Facebook
              </span>
            </li>
            <li>Select the Facebook Page you just created</li>
            <li>Confirm the connection</li>
          </ol>
          <Screenshot caption="Linking Facebook Page to Instagram" />
          <Callout type="warning" className="mt-3">
            You MUST have a Facebook Page linked, even if you never post on
            Facebook. The Instagram Graph API requires this connection.
          </Callout>
        </StepCard>

        <StepCard number={5} title="Verify it's working">
          <p>
            Open the Instagram app. You should now see a{" "}
            <span className="font-medium text-foreground">
              Professional dashboard
            </span>{" "}
            option in your profile settings.
          </p>
          <Screenshot caption="Professional dashboard in Instagram settings" />
          <p className="mt-2">
            If you don&apos;t see it, double-check that your account type is set
            to Business or Creator and that a Facebook Page is linked.
          </p>
        </StepCard>
      </div>

      <div className="mt-12 flex items-center justify-between">
        <Link
          href="/setup"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Overview
        </Link>
        <Link
          href="/setup/meta-developer"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Next: Meta Developer
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
