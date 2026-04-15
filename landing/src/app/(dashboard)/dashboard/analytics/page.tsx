import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = {
  title: "Analytics — Storyline AI",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Detailed analytics and insights.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coming Soon</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Detailed analytics with date range filtering, team performance, and
            content insights are planned for Phase 3. In the meantime, check the
            Overview page for key metrics.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
