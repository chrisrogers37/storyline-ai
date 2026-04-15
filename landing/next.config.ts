import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow Telegram Login Widget script
  async headers() {
    return [
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
