import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { PoolHealth } from "@/components/dashboard/media/pool-health";
import { MediaGrid } from "@/components/dashboard/media/media-grid";
import { MediaUploadWrapper } from "@/components/dashboard/media/media-upload-wrapper";

export default async function MediaLibraryPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const { activeChatId, userId } = session;

  const library = await backendFetchJson(
    "media-library?page=1&page_size=20",
    activeChatId!,
    userId,
    { revalidate: 30 }
  );

  const poolHealth = library?.pool_health ?? {
    total_active: 0,
    never_posted: 0,
    posted_once: 0,
    posted_multiple: 0,
    eligible_for_posting: 0,
    by_category: [],
  };

  return (
    <div className="space-y-6">
      <PoolHealth health={poolHealth} />

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <MediaGrid initialData={library ?? {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          categories: [],
          pool_health: poolHealth,
        }} />
        <MediaUploadWrapper categories={library?.categories ?? []} />
      </div>
    </div>
  );
}
