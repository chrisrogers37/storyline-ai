"use client";

import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const UNCATEGORIZED = "__uncategorized__";

const ACCEPTED_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "video/mp4",
  "video/quicktime",
];
const MAX_SIZE = 50 * 1024 * 1024;

interface UploadResult {
  id: string;
  file_name: string;
  category: string;
}

export function MediaUpload({
  categories,
  onUploadComplete,
}: {
  categories: string[];
  onUploadComplete: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>(UNCATEGORIZED);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadFile = useCallback(
    async (file: File) => {
      setError(null);
      setSuccess(null);

      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError(`Unsupported file type: ${file.type}`);
        return;
      }
      if (file.size > MAX_SIZE) {
        setError("File exceeds 50 MB limit");
        return;
      }

      setUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        if (selectedCategory && selectedCategory !== UNCATEGORIZED) {
          formData.append("category", selectedCategory);
        }

        const res = await fetch("/api/dashboard/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Upload failed" }));
          throw new Error(err.detail || err.error || `Upload failed (${res.status})`);
        }

        const result: UploadResult = await res.json();
        setSuccess(`Uploaded: ${result.file_name} (${result.category})`);
        onUploadComplete();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [selectedCategory, onUploadComplete]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    },
    [uploadFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) uploadFile(file);
      e.target.value = "";
    },
    [uploadFile]
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Upload Media</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Category selector */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Category:</label>
          <Select value={selectedCategory} onValueChange={setSelectedCategory}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Uncategorized" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={UNCATEGORIZED}>Uncategorized</SelectItem>
              {categories.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors",
            dragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50",
            uploading && "pointer-events-none opacity-50"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES.join(",")}
            onChange={handleFileSelect}
            className="hidden"
          />
          {uploading ? (
            <p className="text-sm text-muted-foreground">Uploading...</p>
          ) : (
            <>
              <p className="text-sm font-medium">
                Drop a file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                JPG, PNG, GIF, MP4 — max 50 MB
              </p>
            </>
          )}
        </div>

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {success && (
          <p className="text-sm text-success">{success}</p>
        )}
      </CardContent>
    </Card>
  );
}
