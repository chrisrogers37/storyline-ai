import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { TelegramLoginButton } from "@/components/auth/telegram-login-button";
import { siteConfig } from "@/config/site";

export const metadata = {
  title: `Login — ${siteConfig.name}`,
};

export default function LoginPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {siteConfig.name}
        </Link>

        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">{siteConfig.name}</h1>
          <p className="text-muted-foreground text-sm">
            Sign in with your Telegram account to access the dashboard.
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <TelegramLoginButton />
        </div>

        <p className="text-center text-xs text-muted-foreground">
          Only users with an active Storyline AI bot can access the dashboard.
        </p>
      </div>
    </div>
  );
}
