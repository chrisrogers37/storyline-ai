import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AnalyticsSummary {
  total_posts: number;
  posted: number;
  skipped: number;
  rejected: number;
  failed: number;
  success_rate: number;
  avg_per_day: number;
}

export function AnalyticsCards({ summary }: { summary: AnalyticsSummary }) {
  const cards = [
    {
      title: "Total Posts",
      value: summary.total_posts,
      detail: `${summary.avg_per_day.toFixed(1)}/day avg`,
    },
    {
      title: "Success Rate",
      value: `${(summary.success_rate * 100).toFixed(0)}%`,
      detail: `${summary.posted} posted`,
    },
    {
      title: "Skipped",
      value: summary.skipped,
      detail: `${summary.rejected} rejected`,
    },
    {
      title: "Failed",
      value: summary.failed,
      detail: "last 30 days",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
            <p className="text-xs text-muted-foreground mt-1">{card.detail}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
