import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { ReuseChart } from "@/components/dashboard/media/reuse-chart";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default async function ContentReusePage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const { chatId, userId } = session;

  const data = await backendFetchJson(
    "analytics/content-reuse",
    chatId,
    userId,
    { revalidate: 60 }
  );

  const totalActive = data?.total_active ?? 0;
  const reuseRate = Math.round((data?.reuse_rate ?? 0) * 100);
  const neverPosted = data?.never_posted ?? 0;
  const postedOnce = data?.posted_once ?? 0;
  const postedMultiple = data?.posted_multiple ?? 0;
  const neverPostedByCategory = data?.never_posted_by_category ?? [];

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        How effectively your content library is being reused across posts.
      </p>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Reuse Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{reuseRate}%</div>
            <p className="text-xs text-muted-foreground mt-1">
              of content posted 2+ times
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Never Posted
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">{neverPosted}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalActive > 0
                ? `${Math.round((neverPosted / totalActive) * 100)}% of library`
                : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              One-Shot
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-500">
              {postedOnce}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              posted exactly once
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Evergreen
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {postedMultiple}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              reused 2+ times
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ReuseChart
          data={
            data ?? {
              total_active: 0,
              never_posted: 0,
              posted_once: 0,
              posted_multiple: 0,
              reuse_rate: 0,
              never_posted_by_category: [],
            }
          }
        />

        {/* Never-posted by category table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Never-Posted by Category
            </CardTitle>
          </CardHeader>
          <CardContent>
            {neverPostedByCategory.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                All content has been posted at least once.
              </p>
            ) : (
              <div className="space-y-3">
                {neverPostedByCategory.map(
                  (cat: { category: string; dead_count: number }) => (
                    <div
                      key={cat.category}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm font-medium">
                        {cat.category}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {cat.dead_count} items
                      </span>
                    </div>
                  )
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
