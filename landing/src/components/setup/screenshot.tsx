import { Monitor } from "lucide-react"
import { cn } from "@/lib/utils"

interface ScreenshotProps {
  caption: string
  className?: string
}

export function Screenshot({ caption, className }: ScreenshotProps) {
  return (
    <figure className={cn("my-4", className)}>
      <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        <Monitor className="h-5 w-5 shrink-0 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          You should see: <span className="font-medium text-foreground">{caption}</span>
        </span>
      </div>
    </figure>
  )
}
