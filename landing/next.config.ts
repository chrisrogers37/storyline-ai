import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      // Global security headers
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
      // Telegram Login Widget needs 'unsafe-inline' for its injected script
      // and 'unsafe-eval' because telegram-widget.js eval()s the data-onauth handler
      {
        source: "/login",
        headers: [
          {
            key: "Content-Security-Policy",
            value:
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org; frame-src https://oauth.telegram.org;",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
