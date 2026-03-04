import { cn } from "@/lib/utils"

interface ScreenshotProps {
  caption: string
  className?: string
}

export function Screenshot({ caption, className }: ScreenshotProps) {
  return (
    <figure className={cn("my-4", className)}>
      <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/50">
        <span className="text-sm text-muted-foreground">
          Screenshot: {caption}
        </span>
      </div>
      <figcaption className="mt-2 text-center text-xs text-muted-foreground">
        {caption}
      </figcaption>
    </figure>
  )
}
