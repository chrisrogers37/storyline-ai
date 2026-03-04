"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

export const setupSections = [
  { title: "Overview", href: "/setup" },
  { title: "Instagram Account", href: "/setup/instagram" },
  { title: "Meta Developer", href: "/setup/meta-developer" },
  { title: "Google Drive", href: "/setup/google-drive" },
  { title: "Organize Media", href: "/setup/media-organize" },
  { title: "Connect Telegram", href: "/setup/connect" },
]

export function SetupNav({ className }: { className?: string }) {
  const pathname = usePathname()

  return (
    <nav className={cn("flex flex-col gap-1", className)}>
      {setupSections.map((section) => {
        const isActive = pathname === section.href
        return (
          <Link
            key={section.href}
            href={section.href}
            className={cn(
              "whitespace-nowrap rounded-md px-3 py-2 text-sm transition-colors",
              isActive
                ? "bg-primary/10 font-medium text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {section.title}
          </Link>
        )
      })}
    </nav>
  )
}
