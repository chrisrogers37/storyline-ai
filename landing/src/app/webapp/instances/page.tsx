"use client";

/**
 * Telegram Mini App DM entry point — instance picker.
 *
 * Opened via WebApp button in the bot's DM. Uses the same instance
 * selection flow as the web /instances page, but styled for the
 * Telegram WebView.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ImageIcon, Clock, Pause, Play, ChevronRight, MessageCircle } from "lucide-react";
import type { Instance } from "@/lib/types";
import { formatLastPost } from "@/lib/utils";

export default function WebAppInstancePicker() {
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
        if (!res.ok) throw new Error("Select failed");
        router.push("/dashboard");
      } catch {
        setSelecting(null);
        setError("Failed to select instance.");
      }
    },
    [router]
  );

  useEffect(() => {
    fetch("/api/instances")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load");
        return res.json();
      })
      .then((data) => {
        const list: Instance[] = data.instances ?? [];
        setInstances(list);
        setLoading(false);
        if (list.length === 1) {
          selectInstance(list[0].telegram_chat_id);
        }
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [selectInstance]);

  if (loading || (instances.length === 1 && selecting)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground animate-pulse">
          Loading...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
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

  if (instances.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="text-center space-y-4">
          <MessageCircle className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No instances yet. Send /start to the bot in a group chat to create
            one.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <h1 className="mb-4 text-lg font-semibold">Your Instances</h1>
      <div className="space-y-2">
        {instances.map((inst) => (
          <button
            key={inst.telegram_chat_id}
            onClick={() => selectInstance(inst.telegram_chat_id)}
            disabled={selecting !== null}
            className="w-full rounded-lg border bg-card p-3 text-left transition-colors hover:border-primary/50 disabled:opacity-60"
          >
            <div className="flex items-center justify-between">
              <div className="min-w-0 space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">
                    {inst.display_name || `Instance ${inst.telegram_chat_id}`}
                  </span>
                  {inst.is_paused ? (
                    <Pause className="h-3 w-3 text-yellow-500 shrink-0" />
                  ) : (
                    <Play className="h-3 w-3 text-green-500 shrink-0" />
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <ImageIcon className="h-3 w-3" />
                    {inst.media_count}
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
          </button>
        ))}
      </div>
    </div>
  );
}
