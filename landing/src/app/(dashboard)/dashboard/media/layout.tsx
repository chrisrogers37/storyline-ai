import { MediaTabs } from "@/components/dashboard/media/media-tabs";

export default function MediaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Media Management</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse, upload, and manage your content library.
        </p>
      </div>
      <MediaTabs />
      {children}
    </div>
  );
}
