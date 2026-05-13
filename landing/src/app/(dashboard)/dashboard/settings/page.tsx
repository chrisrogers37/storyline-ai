import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { backendFetchJson } from "@/lib/backend";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GeneralTab } from "@/components/dashboard/settings/general-tab";
import { AccountsTab } from "@/components/dashboard/settings/accounts-tab";
import { IntegrationsTab } from "@/components/dashboard/settings/integrations-tab";

export default async function SettingsPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  const { activeChatId, userId } = session;

  const [initData, accountsData] = await Promise.all([
    backendFetchJson("init", activeChatId!, userId, { revalidate: 60 }),
    backendFetchJson("accounts", activeChatId!, userId, { revalidate: 60 }),
  ]);

  const setup = initData?.setup_state ?? {};
  const accounts = accountsData?.accounts ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your posting schedule, accounts, and integrations.
        </p>
      </div>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <GeneralTab
            settings={{
              posts_per_day: setup.posts_per_day ?? 3,
              posting_hours_start: setup.posting_hours_start ?? 9,
              posting_hours_end: setup.posting_hours_end ?? 22,
              is_paused: setup.is_paused ?? false,
              dry_run_mode: setup.dry_run_mode ?? false,
              enable_instagram_api: setup.enable_instagram_api ?? false,
              show_verbose_notifications:
                setup.show_verbose_notifications ?? false,
              media_sync_enabled: setup.media_sync_enabled ?? false,
              enable_ai_captions: setup.enable_ai_captions ?? false,
              repost_ttl_days: setup.repost_ttl_days ?? null,
              skip_ttl_days: setup.skip_ttl_days ?? null,
            }}
          />
        </TabsContent>

        <TabsContent value="accounts">
          <AccountsTab accounts={accounts} />
        </TabsContent>

        <TabsContent value="integrations">
          <IntegrationsTab
            gdriveConnected={setup.gdrive_connected ?? false}
            gdriveEmail={setup.gdrive_email ?? null}
            mediaCount={setup.media_count ?? 0}
            mediaSyncEnabled={setup.media_sync_enabled ?? false}
            mediaSourceType={setup.media_source_type ?? null}
            mediaSourceRoot={setup.media_source_root ?? null}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
