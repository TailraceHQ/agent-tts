import type { Metadata } from "next";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Instrument_Sans, Inter } from "next/font/google";
import { SITE_URL } from "@/lib/site";
import "./global.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "agent-tts",
    template: "%s | agent-tts",
  },
  description:
    "Speak completed Claude Code, Cursor, and Antigravity responses aloud. Summary, closing, brief, or full — without watching the screen.",
  applicationName: "agent-tts",
};

export default function Layout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSans.variable}`}
      suppressHydrationWarning
    >
      <body className="flex min-h-screen flex-col">
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
