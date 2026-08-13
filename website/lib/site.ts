export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://agent-tts.dev"
).replace(/\/$/, "");

export function absoluteUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
