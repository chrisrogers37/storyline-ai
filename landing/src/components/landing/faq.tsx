import { siteConfig } from "@/config/site"
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion"

const faqs = [
  {
    question: "What is Storyline AI?",
    answer:
      "Storyline AI is an Instagram Story scheduling tool that automatically rotates your content library. Connect your Google Drive, set a posting schedule, and approve each story via Telegram before it goes live.",
  },
  {
    question: "Why Telegram instead of a web dashboard?",
    answer:
      "Telegram gives you instant mobile notifications with image previews and one-tap actions. No need to open a separate app or website — approvals happen right in your chat. A web dashboard is planned for later.",
  },
  {
    question: "Do I need to give you my Instagram password?",
    answer:
      "No. Storyline uses the official Instagram Graph API with OAuth, so you authenticate directly with Meta. We never see or store your Instagram password.",
  },
  {
    question: "What content types are supported?",
    answer:
      "Instagram Stories support JPG, PNG, and GIF images. Storyline validates and optimizes each image to meet Instagram's specifications (9:16 aspect ratio, max 100MB) before posting.",
  },
  {
    question: "Can I manage multiple Instagram accounts?",
    answer:
      "Yes. You can connect multiple Instagram accounts and switch between them directly from Telegram. Each account maintains its own posting schedule and content rotation.",
  },
  {
    question: "What happens if I skip or reject a story?",
    answer:
      "Skipped stories go back in the queue for later. Rejected stories are permanently excluded so they never come up again. You have full control over what gets posted.",
  },
  {
    question: "Is my content stored on your servers?",
    answer:
      "No. Your media stays in your Google Drive. Storyline reads from your drive to schedule posts, but your files are never permanently stored on our infrastructure.",
  },
  {
    question: "Who built this?",
    answer: "built-by-chris",
  },
]

export function FAQ() {
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-3xl px-4">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          Frequently Asked Questions
        </h2>
        <Accordion type="single" collapsible className="mt-12">
          {faqs.map((faq, i) => (
            <AccordionItem key={i} value={`faq-${i}`}>
              <AccordionTrigger>{faq.question}</AccordionTrigger>
              <AccordionContent>
                {faq.answer === "built-by-chris" ? (
                  <p className="text-muted-foreground">
                    Storyline AI is built by{" "}
                    <a
                      href={siteConfig.contact.portfolio}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-4 hover:text-foreground"
                    >
                      Chris
                    </a>
                    . Have questions or feedback? Reach out at{" "}
                    <a
                      href={`mailto:${siteConfig.contact.email}`}
                      className="underline underline-offset-4 hover:text-foreground"
                    >
                      {siteConfig.contact.email}
                    </a>
                    .
                  </p>
                ) : (
                  <p className="text-muted-foreground">{faq.answer}</p>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  )
}
