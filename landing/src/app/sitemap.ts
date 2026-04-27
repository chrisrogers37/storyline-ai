import type { MetadataRoute } from "next"
import { siteConfig } from "@/config/site"

export const dynamic = "force-dynamic"

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()
  return [
    {
      url: siteConfig.url,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteConfig.url}/login`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },
  ]
}
