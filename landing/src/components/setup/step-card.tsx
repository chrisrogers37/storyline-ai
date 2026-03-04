import { cn } from "@/lib/utils"

interface StepCardProps {
  number: number
  title: string
  children: React.ReactNode
  className?: string
}

export function StepCard({
  number,
  title,
  children,
  className,
}: StepCardProps) {
  return (
    <div className={cn("relative pl-12", className)}>
      <div className="absolute left-0 top-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
        {number}
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <div className="mt-2 space-y-2 text-muted-foreground">{children}</div>
    </div>
  )
}
