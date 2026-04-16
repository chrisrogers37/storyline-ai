"use client"

import { useState } from "react"
import { Copy, Check } from "lucide-react"
import { cn } from "@/lib/utils"

interface CopyButtonProps {
  value: string
  className?: string
}

export function CopyButton({ value, className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-md bg-muted px-3 py-1.5 font-mono text-sm",
        className
      )}
    >
      <span className="min-w-0 truncate">{value}</span>
      <button
        onClick={handleCopy}
        className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
        aria-label={copied ? "Copied" : "Copy to clipboard"}
      >
        {copied ? (
          <Check className="h-4 w-4 text-green-600" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>
    </span>
  )
}
