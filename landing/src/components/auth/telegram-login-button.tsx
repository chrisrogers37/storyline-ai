"use client";

import { useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";

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
    const botName = process.env.NEXT_PUBLIC_TELEGRAM_BOT_NAME;
    if (!botName || !containerRef.current) return;

    // Expose callback globally for the Telegram widget
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
    container.appendChild(script);

    return () => {
      delete (window as unknown as Record<string, unknown>).__telegram_login_callback;
      container.innerHTML = "";
    };
  }, [handleAuth]);

  return <div ref={containerRef} className="flex justify-center" />;
}
