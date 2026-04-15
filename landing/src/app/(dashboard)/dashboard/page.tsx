import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { AnalyticsCards } from "@/components/dashboard/analytics-cards";
import { PostingChart } from "@/components/dashboard/posting-chart";
import { CategoryBreakdown } from "@/components/dashboard/category-breakdown";
import { RecentActivity } from "@/components/dashboard/recent-activity";

export default async function DashboardPage() {
  // Deduped with layout via React cache() — no extra JWT verification
  const session = await getSession();
  if (!session) redirect("/login");

  const { chatId, userId } = session;

  const [analytics, categories, history] = await Promise.all([
    backendFetchJson("analytics", chatId, userId, { revalidate: 60 }),
    backendFetchJson("analytics/categories?days=30", chatId, userId, { revalidate: 60 }),
    backendFetchJson("history-detail?limit=10", chatId, userId, { revalidate: 60 }),
  ]);

  const summary = analytics?.summary ?? {
    total_posts: 0,
    posted: 0,
    skipped: 0,
    rejected: 0,
    failed: 0,
    success_rate: 0,
    avg_per_day: 0,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Last 30 days of posting activity.
        </p>
      </div>

      <AnalyticsCards summary={summary} />

      <div className="grid gap-6 lg:grid-cols-2">
        <PostingChart data={analytics?.daily_counts ?? []} />
        <CategoryBreakdown categories={categories?.categories ?? []} />
      </div>

      <RecentActivity items={history?.items ?? []} />
    </div>
  );
}
