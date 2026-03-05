import { Circle, CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ChecklistItem {
  label: string
  href?: string
  checked?: boolean
}

interface ChecklistProps {
  items: ChecklistItem[]
  className?: string
}

export function Checklist({ items, className }: ChecklistProps) {
  return (
    <ul className={cn("space-y-3", className)}>
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-3">
          {item.checked ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          ) : (
            <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
          )}
          <span
            className={cn(
              "text-sm",
              item.checked && "text-muted-foreground line-through"
            )}
          >
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  )
}
