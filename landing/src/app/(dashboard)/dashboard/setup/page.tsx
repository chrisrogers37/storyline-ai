import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendPost } from "@/lib/backend";
import { SetupWizard } from "@/components/dashboard/setup-wizard";

export const metadata = {
  title: "Setup — Storyline AI",
};

export default async function SetupPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  const { activeChatId, userId } = session;

  const res = await backendPost("init", activeChatId!, userId);
  const data = res.ok ? await res.json() : null;

  const setupState = data?.setup_state ?? {
    instagram_connected: false,
    gdrive_connected: false,
    media_folder_configured: false,
    media_indexed: false,
    media_count: 0,
    posts_per_day: 3,
    posting_hours_start: 9,
    posting_hours_end: 22,
    onboarding_completed: false,
  };

  if (setupState.onboarding_completed) redirect("/dashboard");

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Setup</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Connect your accounts and configure posting to get started.
        </p>
      </div>
      <SetupWizard initialState={setupState} />
    </div>
  );
}
