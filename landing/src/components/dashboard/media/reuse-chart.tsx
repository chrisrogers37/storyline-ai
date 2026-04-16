"use client";

import type { PieLabelRenderProps } from "recharts";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ReuseData {
  total_active: number;
  never_posted: number;
  posted_once: number;
  posted_multiple: number;
  reuse_rate: number;
  never_posted_by_category: { category: string; dead_count: number }[];
}

const COLORS = [
  "var(--destructive)",  // never posted — red
  "var(--warning)",      // posted once — yellow
  "var(--success)",      // posted multiple — green
];

export function ReuseChart({ data }: { data: ReuseData }) {
  const pieData = [
    { name: "Never Posted", value: data.never_posted },
    { name: "Posted Once", value: data.posted_once },
    { name: "Reused (2+)", value: data.posted_multiple },
  ].filter((d) => d.value > 0);

  if (pieData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Content Reuse Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-8 text-center">
            No content data available.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Content Reuse Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
              label={(props: PieLabelRenderProps) =>
                `${props.name ?? ""} ${(((props.percent as number | undefined) ?? 0) * 100).toFixed(0)}%`
              }
              labelLine={false}
            >
              {pieData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
