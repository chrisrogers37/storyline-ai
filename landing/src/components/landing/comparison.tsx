"use client"

import { useEffect, useRef } from "react"
import { Check, X } from "lucide-react"
import { trackEvent } from "@/lib/analytics"

const rows = [
  {
    feature: "Built for",
    storydump: "Instagram Stories",
    others: "Feeds, Reels, Stories (afterthought)",
  },
  {
    feature: "Approvals",
    storydump: "In Telegram — instant, mobile",
    others: "Log into web dashboard",
  },
  {
    feature: "Your content",
    storydump: "Stays in Google Drive",
    others: "Uploaded to their servers",
  },
  {
    feature: "Content recycling",
    storydump: "Automatic rotation",
    others: "Manual re-scheduling",
  },
  {
    feature: "Price",
    storydump: "Free during beta",
    others: "$15–50/mo",
  },
]

export function Comparison() {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = sectionRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          trackEvent("Comparison Viewed")
          observer.disconnect()
        }
      },
      { threshold: 0.5 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <section ref={sectionRef} className="py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-4">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          Why not just use Buffer?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-muted-foreground">
          Generic schedulers treat Stories as an afterthought. Storydump is built
          entirely around them.
        </p>
        <div className="mt-12 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="pb-3 pr-4 font-medium text-muted-foreground" />
                <th className="pb-3 pr-4 font-semibold">Storydump</th>
                <th className="pb-3 font-semibold text-muted-foreground">
                  Buffer / Later
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.feature} className="border-b last:border-0">
                  <td className="py-3 pr-4 font-medium">{row.feature}</td>
                  <td className="py-3 pr-4">
                    <span className="flex items-center gap-2">
                      <Check className="h-4 w-4 shrink-0 text-green-600" />
                      {row.storydump}
                    </span>
                  </td>
                  <td className="py-3 text-muted-foreground">
                    <span className="flex items-center gap-2">
                      <X className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                      {row.others}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
