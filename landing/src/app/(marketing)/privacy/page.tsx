import type { Metadata } from "next"
import Link from "next/link"
import { siteConfig } from "@/config/site"

const LAST_UPDATED = "May 13, 2026"

export const metadata: Metadata = {
  title: "Privacy Policy — Storydump",
  description: "How Storydump collects, uses, and protects your data.",
  alternates: { canonical: "/privacy" },
}

export default function PrivacyPolicy() {
  const email = siteConfig.contact.email

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: {LAST_UPDATED}
      </p>
      <p className="mt-4 text-lg text-muted-foreground">
        This policy explains what data Storydump collects, why we collect it,
        how we use it, and the rights you have. It applies to{" "}
        <span className="font-medium text-foreground">storydump.app</span>, the
        Storydump dashboard, and the Storydump Telegram bot.
      </p>

      <div className="mt-10 space-y-10 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="text-xl font-semibold text-foreground">1. Who we are</h2>
          <p className="mt-3">
            Storydump (&quot;Storydump&quot;, &quot;we&quot;, &quot;us&quot;) is
            an independent project operated by Christopher Rogers. For any
            privacy question or request, contact{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>
            . For the purposes of GDPR, this contact also serves as our data
            protection point of contact.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">2. Scope</h2>
          <p className="mt-3">
            This policy covers the marketing site at storydump.app, the
            authenticated dashboard, the Storydump Telegram bot, and the
            background workers that perform scheduling and posting on your
            behalf. Third-party services we integrate with (Telegram, Meta /
            Instagram, Google) operate under their own privacy policies, which
            we link to below.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            3. Information we collect
          </h2>
          <p className="mt-3">We collect only what we need to operate the service:</p>
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>
              <span className="font-medium text-foreground">Account data</span>{" "}
              — from the Telegram Login Widget when you sign in: Telegram user
              ID, username, display name, and profile photo URL.
            </li>
            <li>
              <span className="font-medium text-foreground">
                Google Drive content
              </span>{" "}
              — only when you explicitly grant the Google Drive scope during
              setup. We read file metadata (id, name, MIME type, size, parent
              folder) and the file bytes needed to render and post a Story. We
              do not store the original Drive bytes long-term; we store
              references (Drive file IDs) plus thumbnails and the rendered
              variants needed to post.
            </li>
            <li>
              <span className="font-medium text-foreground">
                Instagram / Meta data
              </span>{" "}
              — long-lived access tokens for the Instagram Business account you
              connect, the account ID, and posting history (post IDs,
              timestamps, results).
            </li>
            <li>
              <span className="font-medium text-foreground">Operational data</span>{" "}
              — queues, schedules, content mix preferences, caption style
              settings, and posting history.
            </li>
            <li>
              <span className="font-medium text-foreground">Technical data</span>{" "}
              — IP address, user-agent, and request timestamps in server logs
              (retained for 30 days, then deleted).
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            4. Google user data — Limited Use disclosure
          </h2>
          <p className="mt-3">
            Storydump&apos;s use and transfer of information received from
            Google APIs to any other app will adhere to the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-foreground"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
          <p className="mt-3 font-medium text-foreground">
            Permitted uses of Google Drive data in Storydump:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>
              Listing files and folders inside the folder(s) you select so you
              can build a posting queue.
            </li>
            <li>
              Reading the bytes of those files to render and post them to your
              own Instagram account on your behalf.
            </li>
            <li>
              Storing metadata (file IDs, names, MIME types) so the same media
              can be re-queued without re-downloading.
            </li>
          </ul>
          <p className="mt-3 font-medium text-foreground">
            Prohibited uses (we never do any of these):
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Selling or transferring Google user data.</li>
            <li>
              Using Google user data for advertising, retargeting, or personalized
              advertising.
            </li>
            <li>
              Allowing humans to read Google user data, unless we have your
              explicit consent for a specific file, it is necessary for security
              (e.g., investigating abuse), it is required by law, or the data
              has been aggregated and anonymized for internal operations.
            </li>
            <li>
              Using Google user data to develop, improve, or train generalized
              machine learning models.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            5. How we use information
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>To operate the service — schedule and publish your Stories.</li>
            <li>To authenticate you and keep your session secure.</li>
            <li>To send service-related notifications via Telegram.</li>
            <li>To debug, monitor reliability, and prevent abuse.</li>
            <li>
              To comply with legal obligations, including responding to lawful
              requests.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            6. Legal bases for processing (GDPR Article 6)
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>
              <span className="font-medium text-foreground">Contract</span> —
              processing necessary to deliver the service you signed up for.
            </li>
            <li>
              <span className="font-medium text-foreground">Consent</span> —
              connecting Google Drive and Instagram (you may withdraw at any
              time).
            </li>
            <li>
              <span className="font-medium text-foreground">
                Legitimate interest
              </span>{" "}
              — security, abuse prevention, and operating the service
              efficiently.
            </li>
            <li>
              <span className="font-medium text-foreground">Legal obligation</span>{" "}
              — responding to valid legal process.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            7. Sharing &amp; sub-processors
          </h2>
          <p className="mt-3">
            We do not sell or rent your personal data. We share data only with
            the sub-processors below, each strictly to deliver the service:
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 pr-4 font-medium text-foreground">
                    Sub-processor
                  </th>
                  <th className="py-2 pr-4 font-medium text-foreground">
                    Purpose
                  </th>
                  <th className="py-2 font-medium text-foreground">Location</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-2 pr-4">Vercel</td>
                  <td className="py-2 pr-4">Landing site &amp; dashboard hosting</td>
                  <td className="py-2">US / global</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">Neon</td>
                  <td className="py-2 pr-4">PostgreSQL database</td>
                  <td className="py-2">US (configurable)</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">Railway</td>
                  <td className="py-2 pr-4">Worker &amp; API hosting</td>
                  <td className="py-2">US</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">Telegram</td>
                  <td className="py-2 pr-4">Chat &amp; bot platform</td>
                  <td className="py-2">Global</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">Meta (Instagram Graph API)</td>
                  <td className="py-2 pr-4">Posting to Instagram</td>
                  <td className="py-2">Global</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">Google (Drive API)</td>
                  <td className="py-2 pr-4">Media sync from Drive</td>
                  <td className="py-2">Global</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4">Plausible Analytics</td>
                  <td className="py-2 pr-4">
                    Privacy-friendly site analytics (cookieless)
                  </td>
                  <td className="py-2">EU</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            We may also disclose data when required by law, to enforce our terms,
            or to protect the rights, property, or safety of users or the public.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            8. Cookies &amp; local storage
          </h2>
          <p className="mt-3">
            Storydump avoids non-essential tracking. The following are used:
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 pr-4 font-medium text-foreground">Name</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Type</th>
                  <th className="py-2 pr-4 font-medium text-foreground">
                    Purpose
                  </th>
                  <th className="py-2 font-medium text-foreground">Retention</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-2 pr-4">
                    <code className="rounded bg-muted px-1.5 py-0.5">
                      storydump_session
                    </code>
                  </td>
                  <td className="py-2 pr-4">HttpOnly cookie</td>
                  <td className="py-2 pr-4">Authenticated session</td>
                  <td className="py-2">24 hours</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-4">
                    <code className="rounded bg-muted px-1.5 py-0.5">
                      storydump-waitlist-registered
                    </code>
                  </td>
                  <td className="py-2 pr-4">localStorage</td>
                  <td className="py-2 pr-4">
                    Suppress waitlist form re-prompt
                  </td>
                  <td className="py-2">Until cleared</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4">Plausible</td>
                  <td className="py-2 pr-4">None (cookieless)</td>
                  <td className="py-2 pr-4">Aggregate analytics</td>
                  <td className="py-2">—</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            The session cookie is strictly necessary to keep you logged in;
            Plausible does not set cookies or fingerprint visitors. We do not
            use advertising or cross-site tracking cookies, so we do not display
            a cookie banner.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            9. Data retention
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>
              <span className="font-medium text-foreground">OAuth tokens</span> —
              until you disconnect the integration or after 6 months of account
              inactivity.
            </li>
            <li>
              <span className="font-medium text-foreground">Posting history</span>{" "}
              — 24 months, then anonymized.
            </li>
            <li>
              <span className="font-medium text-foreground">Server logs</span> —
              30 days.
            </li>
            <li>
              <span className="font-medium text-foreground">
                Queue &amp; media references
              </span>{" "}
              — until you delete them.
            </li>
            <li>
              <span className="font-medium text-foreground">Backups</span> — 30
              days rolling.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">10. Your rights</h2>
          <p className="mt-3 font-medium text-foreground">
            If you are in the EEA, UK, or Switzerland (GDPR):
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Access — request a copy of the data we hold about you.</li>
            <li>Rectification — correct inaccurate data.</li>
            <li>Erasure — request deletion (subject to legal exceptions).</li>
            <li>Restriction — limit how we process your data.</li>
            <li>Portability — receive your data in a portable format.</li>
            <li>Objection — object to processing based on legitimate interest.</li>
            <li>Withdraw consent — at any time, without affecting prior processing.</li>
            <li>
              Lodge a complaint — with your local supervisory authority.
            </li>
          </ul>
          <p className="mt-3 font-medium text-foreground">
            If you are a California resident (CCPA / CPRA):
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Right to know what personal information we collect.</li>
            <li>Right to delete personal information.</li>
            <li>Right to correct inaccurate personal information.</li>
            <li>
              Right to opt out of &quot;sale&quot; or &quot;sharing&quot; of
              personal information. Storydump does not sell or share personal
              information as those terms are defined under the CCPA.
            </li>
            <li>Right to non-discrimination for exercising your rights.</li>
          </ul>
          <p className="mt-3 font-medium text-foreground">Children (COPPA):</p>
          <p className="mt-2">
            Storydump is not directed to children under 13, and we do not
            knowingly collect personal information from children under 13. If
            you believe we have collected such data, contact us and we will
            delete it.
          </p>
          <p className="mt-3">
            To exercise any of these rights, email{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>
            . We respond within 30 days.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            11. International transfers
          </h2>
          <p className="mt-3">
            Our sub-processors operate globally. Where data is transferred
            outside the EEA, UK, or Switzerland, we rely on Standard Contractual
            Clauses or equivalent safeguards published by those sub-processors.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">12. Security</h2>
          <p className="mt-3">
            We use TLS in transit, encryption at rest via our database provider,
            scoped access tokens, and the principle of least privilege. No
            system is perfectly secure; if you believe you have found a security
            issue, please email{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            13. Revoking Google Drive access
          </h2>
          <p className="mt-3">
            You can disconnect Google Drive at any time from inside the
            Storydump dashboard. To fully revoke Storydump&apos;s access at
            Google, also visit{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-foreground"
            >
              myaccount.google.com/permissions
            </a>{" "}
            and remove Storydump.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            14. Account deletion
          </h2>
          <p className="mt-3">
            To request deletion of your Storydump account and associated data,
            email{" "}
            <a
              href={`mailto:${email}`}
              className="underline underline-offset-4 hover:text-foreground"
            >
              {email}
            </a>{" "}
            from the email address linked to your account, or contact us via
            the Storydump Telegram bot. We complete deletion within 30 days,
            subject to backup retention windows and any legal hold.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">
            15. Changes to this policy
          </h2>
          <p className="mt-3">
            We may update this policy from time to time. Material changes will
            be announced via the Storydump Telegram bot and via an in-app
            notice. The &quot;Last updated&quot; date at the top of this page
            always reflects the most recent revision.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-foreground">16. Contact</h2>
          <p className="mt-3">
            Questions, requests, or complaints can be sent to{" "}
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
            href="/terms"
            className="underline underline-offset-4 hover:text-foreground"
          >
            Terms of Service
          </Link>
          .
        </p>
      </div>
    </div>
  )
}
