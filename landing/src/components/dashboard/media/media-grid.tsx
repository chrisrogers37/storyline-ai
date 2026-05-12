"use client";

import { useCallback, useEffect, useState } from "react";
import { getApi } from "@/lib/dashboard-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MediaItem {
  id: string;
  file_name: string;
  category: string;
  mime_type: string;
  file_size: number;
  times_posted: number;
  last_posted_at: string | null;
  source_type: string;
  has_thumbnail: boolean;
  created_at: string;
}

interface MediaLibraryResponse {
  items: MediaItem[];
  total: number;
  page: number;
  page_size: number;
  categories: string[];
  pool_health: {
    total_active: number;
    never_posted: number;
    posted_once: number;
    posted_multiple: number;
    eligible_for_posting: number;
    by_category: { name: string; count: number }[];
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function postingBadge(times: number) {
  if (times === 0)
    return <Badge variant="outline" className="text-xs">Never posted</Badge>;
  if (times === 1)
    return <Badge variant="secondary" className="text-xs">Posted once</Badge>;
  return (
    <Badge className="text-xs bg-green-600 hover:bg-green-700">
      {times}x posted
    </Badge>
  );
}

export function MediaGrid({
  initialData,
}: {
  initialData: MediaLibraryResponse;
}) {
  const [data, setData] = useState(initialData);
  const [poolHealth, setPoolHealth] = useState(initialData.pool_health);
  const [page, setPage] = useState(initialData.page);
  const [category, setCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchPage = useCallback(
    async (p: number, cat: string | null) => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ page: String(p), page_size: "20" });
        if (cat) params.set("category", cat);
        const result = await getApi(`media-library?${params}`);
        // Pool health is only returned on page 1
        if (result.pool_health) setPoolHealth(result.pool_health);
        setData(result);
        setPage(p);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleCategoryFilter = (cat: string | null) => {
    setCategory(cat);
    fetchPage(1, cat);
  };

  const totalPages = Math.ceil(data.total / data.page_size);

  return (
    <div className="space-y-4">
      {/* Category filter */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={category === null ? "default" : "outline"}
          size="sm"
          onClick={() => handleCategoryFilter(null)}
        >
          All ({poolHealth.total_active})
        </Button>
        {poolHealth.by_category.map((cat) => (
          <Button
            key={cat.name}
            variant={category === cat.name ? "default" : "outline"}
            size="sm"
            onClick={() => handleCategoryFilter(cat.name)}
          >
            {cat.name} ({cat.count})
          </Button>
        ))}
      </div>

      {/* Items grid */}
      <div
        className={cn(
          "grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
          loading && "opacity-50 pointer-events-none"
        )}
      >
        {data.items.length === 0 ? (
          <p className="col-span-full text-center text-sm text-muted-foreground py-12">
            No media items found.
          </p>
        ) : (
          data.items.map((item) => (
            <Card key={item.id} className="overflow-hidden">
              <div className="bg-muted h-32 relative flex items-center justify-center text-muted-foreground overflow-hidden">
                {item.has_thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`/api/dashboard/media/${item.id}/thumbnail`}
                    alt={item.file_name}
                    loading="lazy"
                    className="absolute inset-0 h-full w-full object-cover"
                    onError={(e) => {
                      // Proxy returns 404 when the stored Drive URL has
                      // rotated; the next sync refreshes it. Fall back to
                      // the MIME label rather than a broken-image icon.
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : null}
                <span className="text-xs uppercase tracking-wider pointer-events-none">
                  {item.mime_type?.split("/")[1] || "file"}
                </span>
              </div>
              <CardContent className="p-3 space-y-2">
                <p
                  className="text-sm font-medium truncate"
                  title={item.file_name}
                >
                  {item.file_name}
                </p>
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs">
                    {item.category}
                  </Badge>
                  {postingBadge(item.times_posted)}
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{formatBytes(item.file_size)}</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-muted-foreground">
            Showing {(page - 1) * data.page_size + 1}-
            {Math.min(page * data.page_size, data.total)} of {data.total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => fetchPage(page - 1, category)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => fetchPage(page + 1, category)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
