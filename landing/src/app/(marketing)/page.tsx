import { Hero } from "@/components/landing/hero"
import { HowItWorks } from "@/components/landing/how-it-works"
import { TelegramPreview } from "@/components/landing/telegram-preview"
import { Features } from "@/components/landing/features"
import { Pricing } from "@/components/landing/pricing"
import { FAQ } from "@/components/landing/faq"
import { FinalCTA } from "@/components/landing/final-cta"

export default function Home() {
  return (
    <>
      <Hero />
      <HowItWorks />
      <TelegramPreview />
      <Features />
      <Pricing />
      <FAQ />
      <FinalCTA />
    </>
  )
}
