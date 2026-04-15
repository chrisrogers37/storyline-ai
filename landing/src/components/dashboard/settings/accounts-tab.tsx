"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { postApi, getApi } from "@/lib/dashboard-api";

interface Account {
  id: string;
  display_name: string;
  instagram_username: string;
  is_active: boolean;
}

interface AccountsTabProps {
  accounts: Account[];
}

export function AccountsTab({ accounts }: AccountsTabProps) {
  const router = useRouter();
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  async function switchAccount(accountId: string) {
    setLoadingAction(`switch-${accountId}`);
    try {
      await postApi("switch-account", { account_id: accountId });
      router.refresh();
    } catch {
      // ignore
    } finally {
      setLoadingAction(null);
    }
  }

  async function removeAccount(accountId: string) {
    setLoadingAction(`remove-${accountId}`);
    try {
      await postApi("remove-account", { account_id: accountId });
      router.refresh();
    } catch {
      // ignore
    } finally {
      setLoadingAction(null);
    }
  }

  async function connectInstagram() {
    setConnecting(true);
    try {
      const data = await getApi("oauth-url/instagram");
      if (data.auth_url) {
        window.open(data.auth_url, "_blank");
      }
    } catch {
      // ignore
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="space-y-6 pt-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Instagram Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No Instagram accounts connected.
            </p>
          ) : (
            <div className="space-y-3">
              {accounts.map((account) => (
                <div
                  key={account.id}
                  className="flex items-center justify-between gap-4 rounded-lg border p-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">
                        {account.display_name}
                      </p>
                      {account.is_active && (
                        <Badge variant="secondary" className="bg-green-100 text-green-800">
                          Active
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      @{account.instagram_username}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {!account.is_active && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => switchAccount(account.id)}
                        disabled={loadingAction === `switch-${account.id}`}
                      >
                        {loadingAction === `switch-${account.id}`
                          ? "Switching..."
                          : "Switch"}
                      </Button>
                    )}
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button variant="destructive" size="sm">
                          Remove
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Remove Account</DialogTitle>
                          <DialogDescription>
                            Remove @{account.instagram_username}? This will
                            disconnect the account and stop all scheduled posts.
                          </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                          <DialogClose asChild>
                            <Button variant="outline">Cancel</Button>
                          </DialogClose>
                          <Button
                            variant="destructive"
                            onClick={() => removeAccount(account.id)}
                            disabled={loadingAction === `remove-${account.id}`}
                          >
                            {loadingAction === `remove-${account.id}`
                              ? "Removing..."
                              : "Remove"}
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4">
            <Button onClick={connectInstagram} disabled={connecting}>
              {connecting ? "Connecting..." : "Connect Instagram"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
