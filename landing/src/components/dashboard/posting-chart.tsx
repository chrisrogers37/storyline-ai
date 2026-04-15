"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DailyCount {
  date: string;
  posted: number;
  skipped: number;
  rejected: number;
}

export function PostingChart({ data }: { data: DailyCount[] }) {
  // Format date labels to be shorter
  const formatted = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Daily Posting Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {formatted.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No posting data yet.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={formatted}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
              <Tooltip />
              <Bar
                dataKey="posted"
                stackId="a"
                fill="hsl(142, 76%, 36%)"
                name="Posted"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="skipped"
                stackId="a"
                fill="hsl(48, 96%, 53%)"
                name="Skipped"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="rejected"
                stackId="a"
                fill="hsl(0, 84%, 60%)"
                name="Rejected"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
