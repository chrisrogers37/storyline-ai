import type { Metadata } from "next"
import Link from "next/link"
import { siteConfig } from "@/config/site"

const LAST_UPDATED = "May 13, 2026"

export const metadata: Metadata = {
  title: "Terms of Service — Storydump",
  description:
    "The terms that govern your use of Storydump, the Instagram Story scheduler powered by Telegram.",
  alternates: { canonical: "/terms" },
}

export default function TermsOfService() {
  const email = siteConfig.contact.email

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: {LAST_UPDATED}
      </p>
      <p className="mt-4 text-lg text-muted-foreground">
        These Terms govern your use of Storydump, including{" "}
        <span className="font-medium text-foreground">storydump.app</span>, the
        Storydump dashboard, and the Storydump Telegram bot (together, the
        &quot;Service&quot;). By using the Service, you agree to these Terms.
      </p>

      <div className="mt-10 space-y-10 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="text-xl font-semibold text-foreground">
            1. Acceptance of terms
          </h2>
          <p className="mt-3">
            By accessing or using Storydump, you agree to be bound by these
            Terms and by our{" "}
            <Link
              href="/privacy"
              className="underline underline-offset-4 hover:text-foreground"
            >
              Privacy Policy
            </Link>
            . If you do not agree, do not use the Service.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            2. Description of service
          </h2>
          <p className="mt-3">
            Storydump is an Instagram Story scheduling and automation tool. It
            can post on your behalf through the Instagram Graph API, with
            optional Google Drive integration for media sync. Operator
            notifications and team interactions are handled through Telegram.
            Storydump is offered as a hosted service and as self-hostable
            software.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">3. Eligibility</h2>
          <p className="mt-3">
            You must be at least 13 years old to use Storydump, or older if
            required by the laws of your country to consent to processing of
            your personal data. You must have the legal capacity to enter into
            these Terms. You must comply with the terms of every third-party
            platform you connect, including Instagram, Meta, Telegram, and
            Google.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            4. Account &amp; authentication
          </h2>
          <p className="mt-3">
            You sign in to Storydump using the Telegram Login Widget. You are
            responsible for the security of your Telegram account and the
            devices that have access to it. Notify us promptly at{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>{" "}
            if you suspect unauthorized access.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            5. Third-party services
          </h2>
          <p className="mt-3">
            Storydump relies on Instagram (Meta), Telegram, and optionally
            Google Drive. By using Storydump you authorize us to act on your
            behalf in those services within the scopes you grant during setup.
            Storydump is not affiliated with, endorsed by, or sponsored by Meta,
            Google, or Telegram. Each third party&apos;s availability, pricing,
            and policies are outside our control, and changes there may affect
            the Service.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">6. Your content</h2>
          <p className="mt-3">
            You retain all rights to the media, captions, and other content you
            upload or sync into Storydump (&quot;Your Content&quot;). You grant
            Storydump a worldwide, non-exclusive, royalty-free license to host,
            store, transmit, render, and post Your Content solely to operate
            the Service on your behalf. You represent and warrant that you own
            or have the necessary rights to Your Content, that posting it does
            not violate any law or third-party right, and that it does not
            include the personal data of others without their consent.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            7. Acceptable use
          </h2>
          <p className="mt-3">You agree not to:</p>
          <ul className="mt-2 list-disc space-y-2 pl-6">
            <li>
              Use the Service to send spam, harass, or post hateful, harmful,
              fraudulent, deceptive, or illegal content.
            </li>
            <li>
              Circumvent rate limits, integrity systems, or platform policies of
              Instagram, Meta, Telegram, or Google.
            </li>
            <li>
              Reverse engineer, decompile, or attempt to extract source code,
              except to the extent permitted by law.
            </li>
            <li>
              Probe, scan, or test the vulnerability of the Service, or breach
              authentication or security measures.
            </li>
            <li>
              Use the Service to compete with Storydump or to build a
              competing product.
            </li>
            <li>
              Use the Service in any way that could harm minors or expose them
              to inappropriate content.
            </li>
          </ul>
          <p className="mt-3">
            We may suspend or terminate accounts that violate this section,
            with or without notice.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            8. Service availability
          </h2>
          <p className="mt-3">
            The Service is provided on an &quot;as is&quot; and &quot;as
            available&quot; basis. We do not offer a service-level agreement.
            We may perform scheduled or unscheduled maintenance, and outages or
            failures of third-party platforms (Instagram, Telegram, Google) may
            affect Storydump.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            9. Beta features
          </h2>
          <p className="mt-3">
            Some Storydump features are gated behind feature flags (for example,
            direct Instagram API posting under{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">
              ENABLE_INSTAGRAM_API
            </code>
            ). Beta features are provided for evaluation purposes, may change
            or be removed at any time, and are not subject to any availability
            commitments.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">10. Termination</h2>
          <p className="mt-3">
            You may stop using the Service at any time and request account
            deletion as described in our{" "}
            <Link
              href="/privacy"
              className="underline underline-offset-4 hover:text-foreground"
            >
              Privacy Policy
            </Link>
            . We may suspend or terminate your access at our discretion,
            including for violation of these Terms, risk to other users, or
            legal compliance. Sections that by their nature should survive
            termination (including ownership, disclaimers, limitations of
            liability, indemnification, and governing law) will survive.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            11. Disclaimers
          </h2>
          <p className="mt-3">
            To the maximum extent permitted by law, the Service is provided
            without warranties of any kind, whether express, implied, or
            statutory, including warranties of merchantability, fitness for a
            particular purpose, non-infringement, accuracy, or uninterrupted
            operation. We do not warrant that the Service will be error-free or
            that posts will always succeed.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            12. Limitation of liability
          </h2>
          <p className="mt-3">
            To the maximum extent permitted by law, Storydump and its operator
            will not be liable for any indirect, incidental, special,
            consequential, punitive, or exemplary damages, or for lost profits,
            revenue, goodwill, or data, even if advised of the possibility of
            such damages. Our aggregate liability arising out of or relating to
            the Service is limited to the greater of (a) the amounts you paid
            us in the 12 months preceding the event giving rise to liability,
            or (b) US$50.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            13. Indemnification
          </h2>
          <p className="mt-3">
            You will defend, indemnify, and hold harmless Storydump and its
            operator from and against any claims, damages, liabilities, costs,
            and expenses (including reasonable legal fees) arising out of or
            related to (a) Your Content, (b) your use of the Service, (c) your
            violation of these Terms, and (d) your violation of any law or
            third-party right.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            14. Governing law &amp; disputes
          </h2>
          <p className="mt-3">
            {/* TODO: confirm jurisdiction with counsel before launch */}
            These Terms are governed by the laws of the State of New York, USA,
            without regard to its conflict-of-laws rules. Before filing any
            claim, you agree to first attempt to resolve the dispute informally
            by contacting us at{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>{" "}
            and giving us 30 days to respond. If unresolved, exclusive
            jurisdiction lies with the state and federal courts located in New
            York County, New York, and you consent to personal jurisdiction
            there.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            15. Changes to these terms
          </h2>
          <p className="mt-3">
            We may update these Terms from time to time. Material changes will
            be announced via the Storydump Telegram bot and via an in-app
            notice. Your continued use of the Service after a change takes
            effect constitutes acceptance of the updated Terms.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">16. Contact</h2>
          <p className="mt-3">
            Questions about these Terms? Email{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>
            .
          </p>
        </section>
      </div>

      <div className="mt-12 border-t pt-6 text-sm text-muted-foreground">
        <p>
          See also our{" "}
          <Link
            href="/privacy"
            className="underline underline-offset-4 hover:text-foreground"
          >
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </div>
  )
}
