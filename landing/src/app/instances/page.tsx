"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ImageIcon, Clock, Pause, Play, ChevronRight, MessageCircle } from "lucide-react";
import type { Instance } from "@/lib/types";
import { formatLastPost } from "@/lib/utils";

export default function InstancePickerPage() {
  const router = useRouter();
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectInstance = useCallback(
    async (chatId: number) => {
      setSelecting(chatId);
      try {
        const res = await fetch(`/api/instances/${chatId}/select`, {
          method: "POST",
        });
        if (!res.ok) throw new Error("Failed to select instance");
        router.push("/dashboard");
      } catch {
        setSelecting(null);
        setError("Failed to select instance. Please try again.");
      }
    },
    [router]
  );

  useEffect(() => {
    fetch("/api/instances")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load instances");
        return res.json();
      })
      .then((data) => {
        const list: Instance[] = data.instances ?? [];
        setInstances(list);
        setLoading(false);

        // Single instance — auto-select
        if (list.length === 1) {
          selectInstance(list[0].telegram_chat_id);
        }
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [selectInstance]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground animate-pulse">
          Loading instances...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Zero instances — CTA
  if (instances.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="mx-auto max-w-md text-center space-y-6 p-6">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <MessageCircle className="h-8 w-8 text-primary" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight">
              Set up your first instance
            </h1>
            <p className="text-muted-foreground">
              Start a conversation with the Storyline AI bot in Telegram to
              create your first posting instance.
            </p>
          </div>
          <a
            href="https://t.me/storyline_ai_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <MessageCircle className="h-4 w-4" />
            Open Telegram Bot
          </a>
        </div>
      </div>
    );
  }

  // Single instance auto-selects (handled in useEffect), show spinner
  if (instances.length === 1) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground animate-pulse">
          Loading dashboard...
        </div>
      </div>
    );
  }

  // Multiple instances — picker
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="mx-auto w-full max-w-lg space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">
            Choose an instance
          </h1>
          <p className="text-sm text-muted-foreground">
            Select which posting instance to manage.
          </p>
        </div>

        <div className="space-y-3">
          {instances.map((inst) => (
            <button
              key={inst.telegram_chat_id}
              onClick={() => selectInstance(inst.telegram_chat_id)}
              disabled={selecting !== null}
              className="w-full rounded-lg border bg-card p-4 text-left transition-colors hover:border-primary/50 hover:bg-accent disabled:opacity-60 disabled:cursor-wait"
            >
              <div className="flex items-center justify-between">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">
                      {inst.display_name || `Instance ${inst.telegram_chat_id}`}
                    </span>
                    {inst.is_paused ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs font-medium text-yellow-600">
                        <Pause className="h-3 w-3" />
                        Paused
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600">
                        <Play className="h-3 w-3" />
                        Active
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <ImageIcon className="h-3 w-3" />
                      {inst.media_count} media
                    </span>
                    <span>{inst.posts_per_day}/day</span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatLastPost(inst.last_post_at)}
                    </span>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
              </div>
              {selecting === inst.telegram_chat_id && (
                <div className="mt-2 text-xs text-muted-foreground animate-pulse">
                  Selecting...
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
