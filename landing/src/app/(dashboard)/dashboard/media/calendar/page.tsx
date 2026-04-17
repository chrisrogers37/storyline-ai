import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { ContentCalendar } from "@/components/dashboard/media/content-calendar";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default async function CalendarPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const { activeChatId, userId } = session;

  const [history, queue, schedule] = await Promise.all([
    backendFetchJson("history-detail?limit=15", activeChatId!, userId, {
      revalidate: 60,
    }),
    backendFetchJson("queue-detail?limit=10", activeChatId!, userId, {
      revalidate: 30,
    }),
    backendFetchJson("analytics/schedule-preview?slots=15", activeChatId!, userId, {
      revalidate: 60,
    }),
  ]);

  const historyItems = history?.items ?? [];
  const queueItems = queue?.items ?? [];
  const scheduleSlots = schedule?.slots ?? [];

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Posts Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{queue?.posts_today ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              In Queue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {queue?.total_in_flight ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Posting Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {schedule?.posts_per_day ?? 0}/day
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Every {schedule?.interval_minutes ? Math.round(schedule.interval_minutes) : "—"} min
            </p>
          </CardContent>
        </Card>
      </div>

      <ContentCalendar
        history={historyItems}
        queue={queueItems}
        schedule={scheduleSlots}
      />
    </div>
  );
}
