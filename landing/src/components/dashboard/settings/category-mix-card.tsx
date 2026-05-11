"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { postApi } from "@/lib/dashboard-api";

interface CategoryEntry {
  name: string;
  library_count: number;
  configured_ratio: number | null;
}

interface CategoryMixResponse {
  has_explicit_mix: boolean;
  categories: CategoryEntry[];
}

function proportionalSeed(categories: CategoryEntry[]): Record<string, number> {
  const total = categories.reduce((acc, c) => acc + c.library_count, 0);
  if (total === 0) {
    const even = Math.floor(100 / Math.max(categories.length, 1));
    return Object.fromEntries(categories.map((c) => [c.name, even]));
  }
  const raw = categories.map((c) => ({
    name: c.name,
    pct: (c.library_count / total) * 100,
  }));
  const floored = raw.map((r) => ({ ...r, floor: Math.floor(r.pct) }));
  const remainders = floored
    .map((r, i) => ({ i, frac: r.pct - r.floor }))
    .sort((a, b) => b.frac - a.frac);
  let deficit = 100 - floored.reduce((acc, r) => acc + r.floor, 0);
  for (const { i } of remainders) {
    if (deficit <= 0) break;
    floored[i].floor += 1;
    deficit -= 1;
  }
  return Object.fromEntries(floored.map((r) => [r.name, r.floor]));
}

export function CategoryMixCard() {
  const [data, setData] = useState<CategoryMixResponse | null>(null);
  const [localPct, setLocalPct] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res: CategoryMixResponse = await postApi("category-mix");
        if (cancelled) return;
        setData(res);
        setLocalPct(seedFrom(res));
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load category mix");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const total = useMemo(
    () => Object.values(localPct).reduce((a, b) => a + b, 0),
    [localPct]
  );

  const changed = useMemo(() => {
    if (!data) return false;
    if (!data.has_explicit_mix) return true;
    return data.categories.some((c) => {
      const current = Math.round((c.configured_ratio ?? 0) * 100);
      return localPct[c.name] !== current;
    });
  }, [data, localPct]);

  const canSave = !saving && !loading && total === 100 && changed;

  async function handleSave() {
    if (!data) return;
    setError(null);
    setSaving(true);
    try {
      const ratios: Record<string, number> = {};
      for (const c of data.categories) {
        ratios[c.name] = (localPct[c.name] ?? 0) / 100;
      }
      const res: CategoryMixResponse = await postApi("update-category-mix", { ratios });
      setData(res);
      setLocalPct(seedFrom(res));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save mix");
    } finally {
      setSaving(false);
    }
  }

  function handleSlider(name: string, value: number) {
    setLocalPct((prev) => ({ ...prev, [name]: value }));
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Content Mix</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && (
          <p className="text-sm text-muted-foreground">Loading categories…</p>
        )}
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}
        {!loading && data && data.categories.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No categories detected in your library yet. Categories are inferred from
            content-hub folder names — sync some media and they&apos;ll show up here.
          </p>
        )}
        {!loading && data && data.categories.length === 1 && (
          <p className="text-sm text-muted-foreground">
            Only one category detected ({data.categories[0].name}, {data.categories[0].library_count} items).
            Mix weighting kicks in with two or more categories.
          </p>
        )}
        {!loading && data && data.categories.length >= 2 && (
          <>
            {!data.has_explicit_mix && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                No explicit mix set yet. The scheduler is picking from your full library
                without category weighting. Adjust the sliders below and save to control
                the distribution.
              </div>
            )}
            <div className="space-y-4">
              {data.categories.map((c) => (
                <div key={c.name} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="capitalize">{c.name}</Label>
                    <div className="text-sm text-muted-foreground">
                      <span className="font-mono">{localPct[c.name] ?? 0}%</span>
                      <span className="ml-2 text-xs">({c.library_count} items)</span>
                    </div>
                  </div>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={[localPct[c.name] ?? 0]}
                    onValueChange={(v) => handleSlider(c.name, v[0] ?? 0)}
                  />
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between border-t pt-4">
              <div className="text-sm">
                Total:{" "}
                <span
                  className={`font-mono font-medium ${
                    total === 100 ? "text-emerald-600" : "text-red-600"
                  }`}
                >
                  {total}%
                </span>
                {total !== 100 && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    must sum to 100%
                  </span>
                )}
              </div>
              <Button onClick={handleSave} disabled={!canSave}>
                {saving ? "Saving…" : "Save Mix"}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function seedFrom(res: CategoryMixResponse): Record<string, number> {
  if (res.has_explicit_mix) {
    return Object.fromEntries(
      res.categories.map((c) => [c.name, Math.round((c.configured_ratio ?? 0) * 100)])
    );
  }
  return proportionalSeed(res.categories);
}
