"use client"

import { useState, type FormEvent } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface WaitlistFormProps {
  variant?: "hero" | "footer"
  className?: string
}

export function WaitlistForm({ variant = "hero", className }: WaitlistFormProps) {
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<"idle" | "submitting" | "success">("idle")
  const [error, setError] = useState("")

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")

    if (!email || !email.includes("@") || !email.includes(".")) {
      setError("Please enter a valid email address.")
      return
    }

    setStatus("submitting")
    // Phase 03 will replace this with an actual API call
    console.log("Waitlist signup:", email)

    setTimeout(() => {
      setStatus("success")
    }, 1000)
  }

  if (status === "success") {
    return (
      <div
        id={variant === "hero" ? "waitlist" : undefined}
        className={cn("text-center", className)}
        aria-live="polite"
      >
        <p className="text-sm font-medium text-foreground">
          You&apos;re on the list! We&apos;ll be in touch.
        </p>
      </div>
    )
  }

  return (
    <div
      id={variant === "hero" ? "waitlist" : undefined}
      className={cn("w-full", className)}
    >
      <form
        onSubmit={handleSubmit}
        className="mx-auto flex max-w-md flex-col gap-2 sm:flex-row"
        noValidate
      >
        <label htmlFor={`email-${variant}`} className="sr-only">
          Email address
        </label>
        <Input
          id={`email-${variant}`}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={status === "submitting"}
          aria-invalid={error ? true : undefined}
          className="h-10 flex-1"
        />
        <Button
          type="submit"
          size="lg"
          disabled={status === "submitting"}
          className="h-10 whitespace-nowrap"
        >
          {status === "submitting" ? "Joining..." : "Join the Waitlist"}
        </Button>
      </form>
      <div aria-live="polite" className="mt-2 min-h-[1.25rem] text-center">
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
      </div>
    </div>
  )
}
