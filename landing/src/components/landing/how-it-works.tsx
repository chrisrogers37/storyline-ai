import { Cloud, Calendar, Send } from "lucide-react"

const steps = [
  {
    number: 1,
    title: "Connect Your Drive",
    description:
      "Link your Google Drive folder. Storydump indexes your media and keeps everything in sync automatically.",
    icon: Cloud,
  },
  {
    number: 2,
    title: "Set Your Schedule",
    description:
      "Choose how many stories per day and when to post. Smart rotation ensures every piece of content gets its turn.",
    icon: Calendar,
  },
  {
    number: 3,
    title: "Approve via Telegram",
    description:
      "Review each story in Telegram before it goes live. One tap to approve, skip, or reject. You stay in control.",
    icon: Send,
  },
]

export function HowItWorks() {
  return (
    <section className="bg-muted/50 py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-4">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          How It Works
        </h2>
        <div className="relative mt-12 grid gap-8 md:grid-cols-3 md:gap-12">
          {/* Connecting line (desktop only) */}
          <div
            className="absolute top-10 right-[calc(16.67%+1rem)] left-[calc(16.67%+1rem)] hidden border-t-2 border-dashed border-border md:block"
            aria-hidden="true"
          />
          {steps.map((step) => (
            <div key={step.number} className="relative text-center">
              <div className="relative mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-background shadow-sm ring-1 ring-border">
                <step.icon className="h-8 w-8 text-foreground" />
                <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                  {step.number}
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
