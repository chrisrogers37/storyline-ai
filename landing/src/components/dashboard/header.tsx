"use client";

import { useRouter } from "next/navigation";
import type { SessionPayload } from "@/lib/auth";

export function DashboardHeader({ user }: { user: SessionPayload }) {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <h2 className="text-sm font-medium text-muted-foreground">Dashboard</h2>
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
