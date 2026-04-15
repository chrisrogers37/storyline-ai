import { TelegramLoginButton } from "@/components/auth/telegram-login-button";
import { siteConfig } from "@/config/site";

export const metadata = {
  title: `Login — ${siteConfig.name}`,
};

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="mx-auto w-full max-w-sm space-y-8 px-4">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">{siteConfig.name}</h1>
          <p className="text-muted-foreground text-sm">
            Sign in with your Telegram account to access the dashboard.
          </p>
        </div>

        <div className="rounded-lg border bg-card p-8 shadow-sm">
          <TelegramLoginButton />
        </div>

        <p className="text-center text-xs text-muted-foreground">
          Only users with an active Storyline AI bot can access the dashboard.
        </p>
      </div>
    </div>
  );
}
