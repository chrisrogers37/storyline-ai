"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface HistoryItem {
  posted_at: string;
  media_name: string;
  category: string;
  status: string;
  posting_method: string;
}

const statusVariant: Record<string, string> = {
  posted: "bg-green-100 text-green-800",
  skipped: "bg-yellow-100 text-yellow-800",
  rejected: "bg-red-100 text-red-800",
  failed: "bg-red-100 text-red-800",
};

export function RecentActivity({ items }: { items: HistoryItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No activity yet.
          </p>
        ) : (
          <div className="space-y-3">
            {items.map((item, i) => (
              <div
                key={`${item.posted_at}-${i}`}
                className="flex items-center justify-between gap-4 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{item.media_name}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {item.category} &middot;{" "}
                    {new Date(item.posted_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <Badge
                  variant="secondary"
                  className={statusVariant[item.status] || ""}
                >
                  {item.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
