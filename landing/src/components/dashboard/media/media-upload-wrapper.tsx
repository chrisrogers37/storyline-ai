"use client";

import { useRouter } from "next/navigation";
import { MediaUpload } from "./media-upload";

export function MediaUploadWrapper({ categories }: { categories: string[] }) {
  const router = useRouter();

  return (
    <MediaUpload
      categories={categories}
      onUploadComplete={() => router.refresh()}
    />
  );
}
