import { Info, AlertTriangle, Lightbulb } from "lucide-react"
import { cn } from "@/lib/utils"

const variants = {
  info: {
    icon: Info,
    className:
      "border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200",
  },
  warning: {
    icon: AlertTriangle,
    className:
      "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
  },
  tip: {
    icon: Lightbulb,
    className:
      "border-green-200 bg-green-50 text-green-900 dark:border-green-800 dark:bg-green-950 dark:text-green-200",
  },
}

interface CalloutProps {
  type?: "info" | "warning" | "tip"
  children: React.ReactNode
  className?: string
}

export function Callout({ type = "info", children, className }: CalloutProps) {
  const { icon: Icon, className: variantClass } = variants[type]
  return (
    <div
      className={cn(
        "flex gap-3 rounded-lg border p-4",
        variantClass,
        className
      )}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="text-sm">{children}</div>
    </div>
  )
}
