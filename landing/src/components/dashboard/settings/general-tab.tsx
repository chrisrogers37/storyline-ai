"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { postApi } from "@/lib/dashboard-api";
import { CategoryMixCard } from "./category-mix-card";
import { CaptionStyleCard } from "./caption-style-card";
import { RepostCadenceCard } from "./repost-cadence-card";

interface GeneralSettings {
  posts_per_day: number;
  posting_hours_start: number;
  posting_hours_end: number;
  is_paused: boolean;
  dry_run_mode: boolean;
  enable_instagram_api: boolean;
  show_verbose_notifications: boolean;
  media_sync_enabled: boolean;
  enable_ai_captions: boolean;
  send_lifecycle_notifications: boolean | null;
  repost_ttl_days: number | null;
  skip_ttl_days: number | null;
  caption_style: string | null;
}

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => ({
  value: String(i),
  label: i === 0 ? "12 AM" : i < 12 ? `${i} AM` : i === 12 ? "12 PM" : `${i - 12} PM`,
}));

const TOGGLES: { key: keyof GeneralSettings; label: string; description: string }[] = [
  { key: "is_paused", label: "Pause Posting", description: "Temporarily stop all scheduled posts" },
  { key: "dry_run_mode", label: "Dry Run Mode", description: "Simulate posting without publishing" },
  { key: "enable_instagram_api", label: "Instagram API", description: "Use Instagram API for direct posting" },
  { key: "enable_ai_captions", label: "AI Captions", description: "Auto-generate captions with Claude" },
  { key: "show_verbose_notifications", label: "Verbose Notifications", description: "Show detailed Telegram notifications" },
  { key: "send_lifecycle_notifications", label: "Lifecycle Notifications", description: "Receive startup/shutdown messages from the worker" },
  { key: "media_sync_enabled", label: "Media Sync", description: "Auto-sync media from connected sources" },
];

export function GeneralTab({ settings }: { settings: GeneralSettings }) {
  const router = useRouter();
  const [postsPerDay, setPostsPerDay] = useState(settings.posts_per_day);
  const [hoursStart, setHoursStart] = useState(String(settings.posting_hours_start));
  const [hoursEnd, setHoursEnd] = useState(String(settings.posting_hours_end));
  const [toggleState, setToggleState] = useState<Record<string, boolean>>(() => {
    const state: Record<string, boolean> = {};
    for (const t of TOGGLES) {
      state[t.key] = settings[t.key] as boolean;
    }
    return state;
  });
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [togglingKey, setTogglingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const scheduleChanged =
    postsPerDay !== settings.posts_per_day ||
    Number(hoursStart) !== settings.posting_hours_start ||
    Number(hoursEnd) !== settings.posting_hours_end;

  async function saveSchedule() {
    setError(null);
    setSavingSchedule(true);
    try {
      await postApi("schedule", {
        posts_per_day: postsPerDay,
        posting_hours_start: Number(hoursStart),
        posting_hours_end: Number(hoursEnd),
      });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save schedule");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function handleToggle(key: string) {
    setTogglingKey(key);
    const previous = toggleState[key];
    setToggleState((prev) => ({ ...prev, [key]: !prev[key] }));

    try {
      await postApi("toggle-setting", { setting_name: key });
    } catch (e) {
      setToggleState((prev) => ({ ...prev, [key]: previous }));
      setError(e instanceof Error ? e.message : "Failed to toggle setting");
    } finally {
      setTogglingKey(null);
    }
  }

  return (
    <div className="space-y-6 pt-4">
      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800 font-medium">Dismiss</button>
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Posting Schedule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="posts-per-day">Posts per day</Label>
              <Input
                id="posts-per-day"
                type="number"
                min={1}
                max={50}
                value={postsPerDay}
                onChange={(e) => setPostsPerDay(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Start hour</Label>
              <Select value={hoursStart} onValueChange={setHoursStart}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOUR_OPTIONS.map((h) => (
                    <SelectItem key={h.value} value={h.value}>
                      {h.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>End hour</Label>
              <Select value={hoursEnd} onValueChange={setHoursEnd}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOUR_OPTIONS.map((h) => (
                    <SelectItem key={h.value} value={h.value}>
                      {h.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button
            onClick={saveSchedule}
            disabled={!scheduleChanged || savingSchedule || hoursStart === hoursEnd}
          >
            {savingSchedule ? "Saving..." : "Save Schedule"}
          </Button>
        </CardContent>
      </Card>

      <CaptionStyleCard captionStyle={settings.caption_style} onError={setError} />

      <CategoryMixCard />

      <RepostCadenceCard
        repostTtlDays={settings.repost_ttl_days}
        skipTtlDays={settings.skip_ttl_days}
        onError={setError}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Toggles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {TOGGLES.map((toggle, i) => (
            <div key={toggle.key}>
              {i > 0 && <Separator className="mb-4" />}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>{toggle.label}</Label>
                  <p className="text-sm text-muted-foreground">
                    {toggle.description}
                  </p>
                </div>
                <Switch
                  checked={toggleState[toggle.key]}
                  onCheckedChange={() => handleToggle(toggle.key)}
                  disabled={togglingKey === toggle.key}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
