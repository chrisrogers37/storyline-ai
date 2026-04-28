import Link from "next/link"
import { siteConfig } from "@/config/site"

export function Footer() {
  return (
    <footer className="border-t py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground sm:flex-row">
        <p>&copy; {new Date().getFullYear()} {siteConfig.name}</p>
        <p>
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
            Contact
          </a>
          {" "}&middot;{" "}
          <Link
            href="/login"
            className="underline underline-offset-4 hover:text-foreground"
          >
            Sign in
          </Link>
        </p>
      </div>
    </footer>
  )
}
