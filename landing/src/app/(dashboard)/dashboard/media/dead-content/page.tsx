import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { DeadContentChart } from "@/components/dashboard/media/dead-content-chart";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export default async function DeadContentPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const { chatId, userId } = session;

  const data = await backendFetchJson(
    "analytics/dead-content?min_age_days=30",
    chatId,
    userId,
    { revalidate: 60 }
  );

  const totalActive = data?.total_active ?? 0;
  const totalDead = data?.total_dead ?? 0;
  const deadPct = Math.round((data?.dead_percentage ?? 0) * 100);
  const byCategory = data?.by_category ?? [];

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Media items that have been in your library for 30+ days and were never posted.
      </p>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Dead Content
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalDead}</div>
            <Progress value={deadPct} className="mt-2 h-1.5" />
            <p className="text-xs text-muted-foreground mt-1">
              {deadPct}% of library
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Active
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalActive}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalActive - totalDead} have been posted
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Categories Affected
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{byCategory.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              with dead content
            </p>
          </CardContent>
        </Card>
      </div>

      <DeadContentChart data={byCategory} />
    </div>
  );
}
