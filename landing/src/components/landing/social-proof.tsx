const stats = [
  { value: "2,400+", label: "Stories posted" },
  { value: "5,000+", label: "Content items managed" },
  { value: "50+", label: "Active creators" },
]

export function SocialProof() {
  return (
    <section className="border-y bg-muted/50 py-12">
      <div className="mx-auto max-w-5xl px-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          {stats.map((stat) => (
            <div key={stat.label}>
              <p className="text-3xl font-bold tracking-tight">{stat.value}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {stat.label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
