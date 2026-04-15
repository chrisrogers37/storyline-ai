"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface HistoryItem {
  posted_at: string;
  media_name: string;
  category: string;
  status: string;
}

interface ScheduleSlot {
  slot_time: string;
  predicted_category: string | null;
}

interface QueueItem {
  scheduled_for: string;
  media_name: string;
  category: string;
  status: string;
}

interface CalendarDay {
  date: string;
  dayOfMonth: number;
  isToday: boolean;
  isCurrentMonth: boolean;
  posts: { label: string; category: string; type: "past" | "queued" | "predicted" }[];
}

function buildCalendarDays(
  history: HistoryItem[],
  queue: QueueItem[],
  schedule: ScheduleSlot[]
): CalendarDay[] {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();

  // Start from beginning of the month, pad to Monday
  const firstOfMonth = new Date(year, month, 1);
  const startDay = firstOfMonth.getDay();
  const start = new Date(firstOfMonth);
  start.setDate(start.getDate() - ((startDay + 6) % 7)); // Monday start

  // End at end of month, pad to Sunday
  const lastOfMonth = new Date(year, month + 1, 0);
  const endDay = lastOfMonth.getDay();
  const end = new Date(lastOfMonth);
  end.setDate(end.getDate() + (7 - endDay) % 7);

  // Index events by date string
  const postsByDate = new Map<string, CalendarDay["posts"]>();

  for (const item of history) {
    const date = item.posted_at.split("T")[0];
    if (!postsByDate.has(date)) postsByDate.set(date, []);
    postsByDate.get(date)!.push({
      label: item.media_name,
      category: item.category,
      type: "past",
    });
  }

  for (const item of queue) {
    const date = item.scheduled_for.split("T")[0];
    if (!postsByDate.has(date)) postsByDate.set(date, []);
    postsByDate.get(date)!.push({
      label: item.media_name,
      category: item.category,
      type: "queued",
    });
  }

  for (const slot of schedule) {
    const date = slot.slot_time.split("T")[0];
    if (!postsByDate.has(date)) postsByDate.set(date, []);
    postsByDate.get(date)!.push({
      label: slot.predicted_category || "any",
      category: slot.predicted_category || "any",
      type: "predicted",
    });
  }

  const today = now.toISOString().split("T")[0];
  const days: CalendarDay[] = [];
  const current = new Date(start);

  while (current <= end) {
    const dateStr = current.toISOString().split("T")[0];
    days.push({
      date: dateStr,
      dayOfMonth: current.getDate(),
      isToday: dateStr === today,
      isCurrentMonth: current.getMonth() === month,
      posts: postsByDate.get(dateStr) || [],
    });
    current.setDate(current.getDate() + 1);
  }

  return days;
}

const typeColors = {
  past: "bg-green-500/20 text-green-700 dark:text-green-400",
  queued: "bg-blue-500/20 text-blue-700 dark:text-blue-400",
  predicted: "bg-muted text-muted-foreground",
};

export function ContentCalendar({
  history,
  queue,
  schedule,
}: {
  history: HistoryItem[];
  queue: QueueItem[];
  schedule: ScheduleSlot[];
}) {
  const days = useMemo(
    () => buildCalendarDays(history, queue, schedule),
    [history, queue, schedule]
  );

  const weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const monthName = new Date().toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{monthName}</CardTitle>
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-green-500" /> Posted
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-blue-500" /> In Queue
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-muted-foreground" /> Predicted
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {/* Header */}
        <div className="grid grid-cols-7 gap-px mb-1">
          {weekDays.map((d) => (
            <div
              key={d}
              className="text-center text-xs font-medium text-muted-foreground py-1"
            >
              {d}
            </div>
          ))}
        </div>

        {/* Days grid */}
        <div className="grid grid-cols-7 gap-px">
          {days.map((day) => (
            <div
              key={day.date}
              className={cn(
                "min-h-[80px] border rounded-sm p-1",
                !day.isCurrentMonth && "opacity-30",
                day.isToday && "border-primary"
              )}
            >
              <span
                className={cn(
                  "text-xs font-medium",
                  day.isToday && "text-primary"
                )}
              >
                {day.dayOfMonth}
              </span>
              <div className="mt-0.5 space-y-0.5">
                {day.posts.slice(0, 3).map((post, i) => (
                  <div
                    key={i}
                    className={cn(
                      "truncate rounded px-1 py-0.5 text-[10px]",
                      typeColors[post.type]
                    )}
                    title={post.label}
                  >
                    {post.label}
                  </div>
                ))}
                {day.posts.length > 3 && (
                  <div className="text-[10px] text-muted-foreground px-1">
                    +{day.posts.length - 3} more
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
