import { Check } from "lucide-react"
import { Button } from "@/components/ui/button"

const perks = [
  "Unlimited Stories",
  "Google Drive integration",
  "Multi-account support",
  "Telegram-powered workflow",
]

export function Pricing() {
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-4 text-center">
        <h2 className="text-3xl font-bold tracking-tight">
          Free While in Beta
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
          Storydump is free for early adopters. Join now and lock in access
          before launch pricing kicks in.
        </p>
        <ul className="mx-auto mt-8 inline-flex flex-col items-start gap-3 text-left">
          {perks.map((perk) => (
            <li key={perk} className="flex items-center gap-2 text-sm">
              <Check className="h-4 w-4 shrink-0 text-foreground" />
              {perk}
            </li>
          ))}
        </ul>
        <div className="mt-8">
          <Button asChild size="lg">
            <a href="#waitlist">Get Early Access</a>
          </Button>
        </div>
      </div>
    </section>
  )
}
