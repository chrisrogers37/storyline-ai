"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export function TelegramLoginButton() {
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const botName = process.env.NEXT_PUBLIC_TELEGRAM_BOT_NAME;

  const handleAuth = useCallback(
    async (user: TelegramUser) => {
      const res = await fetch("/api/auth/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(user),
      });

      if (res.ok) {
        router.push("/dashboard");
      } else {
        console.error("Login failed:", await res.json());
      }
    },
    [router]
  );

  useEffect(() => {
    if (!botName || !containerRef.current) return;

    setStatus("loading");
    (window as unknown as Record<string, unknown>).__telegram_login_callback = handleAuth;

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botName);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "8");
    script.setAttribute("data-onauth", "__telegram_login_callback(user)");
    script.setAttribute("data-request-access", "write");

    const container = containerRef.current;
    let pollTimer: ReturnType<typeof setInterval>;

    script.onload = () => {
      // Script loaded, but the widget iframe may still not render.
      // Poll until the iframe appears or give up after 5s.
      let elapsed = 0;
      pollTimer = setInterval(() => {
        elapsed += 500;
        if (container.querySelector("iframe")) {
          clearInterval(pollTimer);
          setStatus("ready");
        } else if (elapsed >= 5000) {
          clearInterval(pollTimer);
          setStatus("failed");
        }
      }, 500);
    };
    script.onerror = () => setStatus("failed");

    container.appendChild(script);

    return () => {
      clearInterval(pollTimer);
      delete (window as unknown as Record<string, unknown>).__telegram_login_callback;
      container.innerHTML = "";
    };
  }, [botName, handleAuth]);

  if (!botName) {
    return (
      <div className="min-h-[56px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">
          Telegram login is not configured. Set{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">NEXT_PUBLIC_TELEGRAM_BOT_NAME</code>{" "}
          to enable sign-in.
        </p>
      </div>
    );
  }

  return (
    <div className="relative min-h-[56px] flex items-center justify-center">
      {status === "loading" && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading Telegram login...
        </div>
      )}
      {status === "failed" && (
        <div className="space-y-3 text-center">
          <p className="text-sm text-muted-foreground">
            Telegram widget didn&apos;t load. You can sign in directly:
          </p>
          <a
            href={`https://t.me/${botName}?start=login`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md bg-[#2AABEE] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#229ED9]"
          >
            Open in Telegram
          </a>
        </div>
      )}
      <div ref={containerRef} className={status === "ready" ? "flex justify-center" : "pointer-events-none absolute inset-0 flex justify-center opacity-0"} />
    </div>
  );
}
