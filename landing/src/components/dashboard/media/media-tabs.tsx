"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/dashboard/media", label: "Library" },
  { href: "/dashboard/media/calendar", label: "Calendar" },
  { href: "/dashboard/media/dead-content", label: "Dead Content" },
  { href: "/dashboard/media/reuse", label: "Content Reuse" },
];

export function MediaTabs() {
  const pathname = usePathname();

  return (
    <div className="border-b">
      <nav className="-mb-px flex gap-4" aria-label="Media tabs">
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "border-b-2 px-1 py-2 text-sm font-medium transition-colors",
                active
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:border-muted-foreground/30 hover:text-foreground"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
