type EventProps = Record<string, string | number | boolean>

export const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign"] as const

export function trackEvent(name: string, props?: EventProps) {
  if (typeof window !== "undefined" && window.plausible) {
    window.plausible(name, props ? { props } : undefined)
  }
}

declare global {
  interface Window {
    plausible?: (
      event: string,
      options?: { props?: EventProps }
    ) => void
  }
}
