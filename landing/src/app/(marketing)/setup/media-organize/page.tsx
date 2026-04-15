import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { StepCard } from "@/components/setup/step-card"
import { Callout } from "@/components/setup/callout"

export const metadata: Metadata = {
  title: "Organize Your Media — Storyline AI",
  robots: { index: false, follow: false },
}

export default function MediaOrganize() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Organizing Your Media
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Storyline reads media from your Google Drive. How you organize your
        folders determines your content categories and posting mix.
      </p>

      <div className="mt-10 space-y-10">
        <StepCard number={1} title="Folder structure = categories">
          <p>
            Storyline treats each subfolder in your root media folder as a
            category. Here&apos;s the recommended structure:
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-muted p-4 text-sm">
            {`My Instagram Stories/          ← root folder
├── memes/                     ← category: "memes"
│   ├── funny-cat.jpg
│   ├── monday-mood.png
│   └── ...
├── products/                  ← category: "products"
│   ├── new-tshirt.jpg
│   ├── sale-banner.png
│   └── ...
├── behind-the-scenes/         ← category: "behind-the-scenes"
│   ├── studio-shot.jpg
│   └── ...
└── announcements/             ← category: "announcements"
    ├── holiday-hours.png
    └── ...`}
          </pre>
        </StepCard>

        <StepCard number={2} title="Image requirements">
          <ul className="list-inside list-disc space-y-1">
            <li>
              <span className="font-medium text-foreground">Aspect ratio:</span>{" "}
              9:16 (1080x1920 ideal)
            </li>
            <li>
              <span className="font-medium text-foreground">Formats:</span> JPG,
              PNG, GIF
            </li>
            <li>
              <span className="font-medium text-foreground">Max size:</span>{" "}
              100MB per file
            </li>
          </ul>
          <Callout type="tip" className="mt-3">
            Don&apos;t worry about getting everything perfect. Storyline
            validates each file and will tell you which ones need attention.
          </Callout>
        </StepCard>

        <StepCard number={3} title="Category mixing">
          <p>
            Storyline distributes posts across your categories based on ratios
            you define. For example:
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1">
            <li>70% memes</li>
            <li>20% products</li>
            <li>10% announcements</li>
          </ul>
          <p className="mt-2">
            You can adjust these ratios anytime from Telegram using the settings
            menu.
          </p>
        </StepCard>

        <StepCard number={4} title="How many files do you need?">
          <ul className="list-inside list-disc space-y-1">
            <li>
              <span className="font-medium text-foreground">Minimum:</span> ~30
              files for a week of posting (3/day &times; 7 days + buffer)
            </li>
            <li>
              <span className="font-medium text-foreground">Ideal:</span> 100+
              for good variety
            </li>
          </ul>
          <p className="mt-2">
            Storyline tracks what&apos;s been posted and cycles through your
            library evenly — never-posted content always goes first.
          </p>
        </StepCard>

        <StepCard number={5} title="Tips">
          <ul className="list-inside list-disc space-y-1">
            <li>
              Keep filenames descriptive — they show up when reviewing posts in
              Telegram
            </li>
            <li>
              Remove content you&apos;d never want to post — Storyline will try
              to post everything in the folder
            </li>
            <li>
              You can add or remove files anytime — Storyline syncs
              automatically
            </li>
          </ul>
        </StepCard>
      </div>

      <div className="mt-12 flex items-center justify-between">
        <Link
          href="/setup/google-drive"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Google Drive
        </Link>
        <Link
          href="/setup/connect"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Next: Connect Telegram
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
