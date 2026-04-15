"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { postApi, getApi } from "@/lib/dashboard-api";

interface IntegrationsTabProps {
  gdriveConnected: boolean;
  gdriveEmail: string | null;
  mediaCount: number;
  mediaSyncEnabled: boolean;
}

export function IntegrationsTab({
  gdriveConnected,
  gdriveEmail,
  mediaCount,
  mediaSyncEnabled,
}: IntegrationsTabProps) {
  const router = useRouter();
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [connecting, setConnecting] = useState(false);

  async function connectGdrive() {
    setConnecting(true);
    try {
      const data = await getApi("oauth-url/google-drive");
      if (data.auth_url) {
        window.open(data.auth_url, "_blank");
      }
    } catch {
      // ignore
    } finally {
      setConnecting(false);
    }
  }

  async function disconnectGdrive() {
    setDisconnecting(true);
    try {
      await postApi("disconnect-gdrive");
      router.refresh();
    } catch {
      // ignore
    } finally {
      setDisconnecting(false);
    }
  }

  async function syncMedia() {
    setSyncing(true);
    try {
      await postApi("sync-media");
      router.refresh();
    } catch {
      // ignore
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="space-y-6 pt-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Google Drive</CardTitle>
        </CardHeader>
        <CardContent>
          {gdriveConnected ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">Connected</p>
                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                      Active
                    </Badge>
                  </div>
                  {gdriveEmail && (
                    <p className="text-sm text-muted-foreground">
                      {gdriveEmail}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={syncMedia}
                    disabled={syncing}
                  >
                    {syncing ? "Syncing..." : "Sync Now"}
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={disconnectGdrive}
                    disabled={disconnecting}
                  >
                    {disconnecting ? "Disconnecting..." : "Disconnect"}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-4 text-center">
              <p className="text-sm text-muted-foreground mb-4">
                Connect Google Drive to sync media for posting.
              </p>
              <Button onClick={connectGdrive} disabled={connecting}>
                {connecting ? "Connecting..." : "Connect Google Drive"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Media</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <p className="font-medium">{mediaCount} media files</p>
              <p className="text-sm text-muted-foreground">
                {mediaSyncEnabled ? "Auto-sync enabled" : "Auto-sync disabled"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
