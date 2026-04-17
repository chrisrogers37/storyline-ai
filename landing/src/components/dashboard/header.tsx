"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, ChevronDown, Check } from "lucide-react";
import type { SessionPayload } from "@/lib/auth";
import type { Instance } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "@/components/dashboard/sidebar";

export function DashboardHeader({ user }: { user: SessionPayload }) {
  const router = useRouter();
  const [instances, setInstances] = useState<Pick<Instance, "telegram_chat_id" | "display_name">[]>([]);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/instances")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.instances) setInstances(data.instances);
      })
      .catch((err) => console.warn("Failed to load instances for switcher:", err));
  }, []);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  async function switchInstance(chatId: number) {
    if (chatId === user.activeChatId) {
      setSwitcherOpen(false);
      return;
    }
    setSwitching(true);
    setSwitchError(null);
    try {
      const res = await fetch(`/api/instances/${chatId}/select`, {
        method: "POST",
      });
      if (res.ok) {
        router.refresh();
        setSwitcherOpen(false);
      } else {
        setSwitchError("Failed to switch instance");
      }
    } catch {
      setSwitchError("Failed to switch instance");
    } finally {
      setSwitching(false);
    }
  }

  const currentName =
    instances.find((i) => i.telegram_chat_id === user.activeChatId)
      ?.display_name ?? "Dashboard";

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

        {/* Instance switcher */}
        {instances.length > 1 ? (
          <div className="relative">
            <button
              onClick={() => setSwitcherOpen(!switcherOpen)}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              {currentName}
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {switcherOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setSwitcherOpen(false)}
                />
                <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-md border bg-popover p-1 shadow-md">
                  {instances.map((inst) => (
                    <button
                      key={inst.telegram_chat_id}
                      onClick={() => switchInstance(inst.telegram_chat_id)}
                      disabled={switching}
                      className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-sm hover:bg-accent disabled:opacity-50 transition-colors"
                    >
                      <span className="truncate">
                        {inst.display_name || "Unnamed Instance"}
                      </span>
                      {inst.telegram_chat_id === user.activeChatId && (
                        <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                      )}
                    </button>
                  ))}
                  {switchError && (
                    <p className="px-2 py-1 text-xs text-destructive">
                      {switchError}
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          <h2 className="text-sm font-medium text-muted-foreground">
            {currentName}
          </h2>
        )}
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
