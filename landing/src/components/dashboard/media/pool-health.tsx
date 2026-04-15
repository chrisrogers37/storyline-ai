import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface PoolHealth {
  total_active: number;
  never_posted: number;
  posted_once: number;
  posted_multiple: number;
  eligible_for_posting: number;
  by_category: { name: string; count: number }[];
}

export function PoolHealth({ health }: { health: PoolHealth }) {
  const total = health.total_active || 1;
  const reuseRate = Math.round((health.posted_multiple / total) * 100);
  const eligiblePct = Math.round((health.eligible_for_posting / total) * 100);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total Active
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{health.total_active}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {health.by_category.length} categories
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Eligible for Posting
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{health.eligible_for_posting}</div>
          <Progress value={eligiblePct} className="mt-2 h-1.5" />
          <p className="text-xs text-muted-foreground mt-1">
            {eligiblePct}% of library
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
          <div className="text-2xl font-bold">{health.never_posted}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {Math.round((health.never_posted / total) * 100)}% untouched
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Reuse Rate
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{reuseRate}%</div>
          <p className="text-xs text-muted-foreground mt-1">
            {health.posted_multiple} posted 2+ times
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
