"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { postApi } from "@/lib/dashboard-api";

interface Props {
  captionStyle: string | null;
  onError: (message: string | null) => void;
}

const STYLE_OPTIONS = [
  {
    value: "enhanced",
    label: "Enhanced",
    description: "Emoji headers, separators, and a bold layout.",
  },
  {
    value: "simple",
    label: "Simple",
    description: "Plain-text caption with no extra formatting.",
  },
];

export function CaptionStyleCard({ captionStyle, onError }: Props) {
  const router = useRouter();
  const initial = captionStyle ?? "enhanced";
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);

  const changed = value !== initial;

  async function save() {
    onError(null);
    setSaving(true);
    try {
      await postApi("update-string-setting", {
        setting_name: "caption_style",
        value,
      });
      router.refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to save caption style");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Caption Style</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Telegram notification format</Label>
          <Select value={value} onValueChange={setValue}>
            <SelectTrigger className="w-full sm:w-[260px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STYLE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">
            {STYLE_OPTIONS.find((o) => o.value === value)?.description}
          </p>
        </div>
        <Button onClick={save} disabled={!changed || saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </CardContent>
    </Card>
  );
}
