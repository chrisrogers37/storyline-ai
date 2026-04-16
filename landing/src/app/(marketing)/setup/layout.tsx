import Link from "next/link"
import { ArrowLeft, Mail } from "lucide-react"
import { SetupNav } from "@/components/setup/setup-nav"
import { siteConfig } from "@/config/site"

export default function SetupLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to home
      </Link>

      {/* Mobile nav — scrollable horizontal tabs */}
      <div className="mt-6 -mx-4 px-4 overflow-x-auto md:hidden">
        <SetupNav className="flex-row gap-1 w-max" />
      </div>

      <div className="mt-8 flex gap-12">
        {/* Sidebar (desktop) */}
        <aside className="hidden w-52 shrink-0 md:block">
          <div className="sticky top-20">
            <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Setup Guide
            </p>
            <SetupNav />
          </div>
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {children}

          <div className="mt-12 border-t pt-6">
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Mail className="h-4 w-4" />
              Need help?{" "}
              <a
                href={`mailto:${siteConfig.contact.email}`}
                className="underline underline-offset-4 hover:text-foreground"
              >
                {siteConfig.contact.email}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
