"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface CategoryData {
  category: string;
  posted: number;
  total: number;
  success_rate: number;
  actual_ratio: number;
  configured_ratio: number;
}

export function CategoryBreakdown({ categories }: { categories: CategoryData[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Category Performance</CardTitle>
      </CardHeader>
      <CardContent>
        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No category data yet.
          </p>
        ) : (
          <div className="space-y-4">
            {categories.map((cat) => {
              const drift = Math.abs(cat.actual_ratio - cat.configured_ratio);
              const driftStatus =
                drift < 0.05 ? "text-green-600" : drift < 0.15 ? "text-yellow-600" : "text-red-600";

              return (
                <div key={cat.category} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium capitalize">{cat.category}</span>
                    <span className="text-muted-foreground">
                      {cat.posted}/{cat.total} posted
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{
                          width: `${Math.min(cat.actual_ratio * 100, 100)}%`,
                        }}
                      />
                    </div>
                    <span className={`text-xs font-mono ${driftStatus}`}>
                      {(cat.actual_ratio * 100).toFixed(0)}%
                      <span className="text-muted-foreground">
                        /{(cat.configured_ratio * 100).toFixed(0)}%
                      </span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
