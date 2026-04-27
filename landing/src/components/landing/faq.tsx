"use client"

import { siteConfig } from "@/config/site"
import { faqs } from "@/config/faqs"
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion"
import { trackEvent } from "@/lib/analytics"

export function FAQ() {
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-3xl px-4">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          Frequently Asked Questions
        </h2>
        <Accordion
          type="single"
          collapsible
          className="mt-12"
          onValueChange={(value) => {
            if (value) {
              const idx = parseInt(value.replace("faq-", ""), 10)
              const faq = faqs[idx]
              if (faq) trackEvent("FAQ Expanded", { question: faq.question })
            }
          }}
        >
          {faqs.map((faq, i) => (
            <AccordionItem key={i} value={`faq-${i}`}>
              <AccordionTrigger>{faq.question}</AccordionTrigger>
              <AccordionContent>
                {faq.answer === "built-by-chris" ? (
                  <p className="text-muted-foreground">
                    Storydump is built by{" "}
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
