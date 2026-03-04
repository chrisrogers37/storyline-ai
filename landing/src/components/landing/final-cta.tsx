import { siteConfig } from "@/config/site"
import { WaitlistForm } from "@/components/landing/waitlist-form"

export function FinalCTA() {
  return (
    <section className="bg-muted/50 py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-4 text-center">
        <h2 className="text-3xl font-bold tracking-tight">
          Ready to put your content to work?
        </h2>
        <p className="mt-4 text-muted-foreground">
          Join the waitlist and be first in line.
        </p>
        <div className="mt-8">
          <WaitlistForm variant="footer" />
        </div>
        <p className="mt-8 text-sm text-muted-foreground">
          Built by{" "}
          <a
            href={siteConfig.contact.portfolio}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-foreground"
          >
            Chris
          </a>
          {" "}&middot;{" "}
          <a
            href={`mailto:${siteConfig.contact.email}`}
            className="underline underline-offset-4 hover:text-foreground"
          >
            {siteConfig.contact.email}
          </a>
        </p>
      </div>
    </section>
  )
}
