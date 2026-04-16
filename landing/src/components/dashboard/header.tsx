"use client";

import { useRouter } from "next/navigation";
import { Menu } from "lucide-react";
import type { SessionPayload } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "@/components/dashboard/sidebar";

export function DashboardHeader({ user }: { user: SessionPayload }) {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="flex items-center gap-3">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open navigation</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-56 p-0">
            <Sidebar mobile />
          </SheetContent>
        </Sheet>
        <h2 className="text-sm font-medium text-muted-foreground">Dashboard</h2>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">
          {user.firstName}
          {user.username && (
            <span className="ml-1 text-xs opacity-60">@{user.username}</span>
          )}
        </span>
        <button
          onClick={handleLogout}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
