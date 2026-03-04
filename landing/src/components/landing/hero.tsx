import { WaitlistForm } from "@/components/landing/waitlist-form"

export function Hero() {
  return (
    <section className="py-20 md:py-32">
      <div className="mx-auto max-w-5xl px-4 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Keep Your Stories Alive
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Automatically rotate your content library through Instagram Stories.
          Connect your cloud storage, set a schedule, and approve posts via
          Telegram.
        </p>
        <div className="mt-10">
          <WaitlistForm variant="hero" />
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          Free during beta &middot; No credit card required
        </p>
      </div>
    </section>
  )
}
