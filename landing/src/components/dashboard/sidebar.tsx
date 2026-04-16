"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  CalendarDays,
  ImageIcon,
  LayoutDashboard,
  Rocket,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { siteConfig } from "@/config/site";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/media", label: "Media Library", icon: ImageIcon },
  { href: "/dashboard/media/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
  { href: "/dashboard/setup", label: "Setup Wizard", icon: Rocket },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
];

export function Sidebar({ mobile }: { mobile?: boolean }) {
  const pathname = usePathname();

  return (
    <aside className={mobile ? "w-56 bg-card" : "hidden w-56 shrink-0 border-r bg-card md:block"}>
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
          {siteConfig.name}
        </Link>
      </div>
      <nav className="space-y-1 p-3">
        {navItems.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname === item.href || pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
