"use client";

import { useState } from "react";
import {
  SAMPLE_TURN,
  heardText,
  spokenIds,
  type SpeakMode,
} from "@/lib/speak-demo";

const MODES: { id: SpeakMode; label: string; hint: string }[] = [
  {
    id: "summary",
    label: "summary",
    hint: "First prose paragraph. Default. Often the “I’ll look at that” line.",
  },
  {
    id: "closing",
    label: "closing",
    hint: "Last prose paragraph. Usually the actual result.",
  },
  {
    id: "brief",
    label: "brief",
    hint: "First sentence of the lead paragraph, capped at 20 words.",
  },
  {
    id: "full",
    label: "full",
    hint: "Every cleaned block. Headings and quotes use the header voice.",
  },
];

export function SpeakPreview() {
  const [mode, setMode] = useState<SpeakMode>("summary");
  const ids = spokenIds(mode);
  const heard = heardText(mode);

  return (
    <div className="not-prose my-6 overflow-hidden rounded-xl border border-fd-border bg-fd-card shadow-sm">
      <div className="flex flex-wrap gap-2 border-b border-fd-border px-4 py-3">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              mode === m.id
                ? "bg-[var(--tts-accent)] text-[var(--tts-accent-fg)]"
                : "bg-fd-muted text-fd-muted-foreground hover:text-fd-foreground"
            }`}
          >
            tts {m.label}
          </button>
        ))}
      </div>

      <p className="border-b border-fd-border px-4 py-2 text-sm text-fd-muted-foreground">
        {MODES.find((m) => m.id === mode)?.hint}
      </p>

      <div className="grid gap-0 lg:grid-cols-2">
        <div className="border-b border-fd-border p-4 lg:border-b-0 lg:border-r">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-fd-muted-foreground">
            Agent turn
          </p>
          <div className="space-y-2 font-mono text-[13px] leading-relaxed">
            {SAMPLE_TURN.map((block) => {
              const on = ids.has(block.id);
              const shown =
                mode === "brief" && on && block.brief ? block.brief : block.text;
              const rest =
                mode === "brief" && on && block.brief
                  ? block.text.slice(block.brief.length)
                  : "";
              return (
                <div
                  key={block.id}
                  className={`rounded-md px-3 py-2 transition-colors ${
                    on
                      ? block.voice === "header"
                        ? "bg-[color-mix(in_oklab,var(--tts-header)_22%,transparent)]"
                        : "bg-[color-mix(in_oklab,var(--tts-accent)_18%,transparent)]"
                      : "opacity-40"
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2 text-[10px] font-sans font-semibold uppercase tracking-wide text-fd-muted-foreground">
                    <span>{block.label}</span>
                    <span>·</span>
                    <span>{block.voice} voice</span>
                    <span className="ml-auto">{on ? "spoken" : "skipped"}</span>
                  </div>
                  {block.kind === "heading" ? (
                    <p className="font-sans text-base font-semibold">{shown}</p>
                  ) : block.kind === "code" ? (
                    <p className="italic">{shown}</p>
                  ) : block.kind === "blockquote" ? (
                    <p className="border-l-2 border-current pl-2">{shown}</p>
                  ) : (
                    <p>
                      <span>{shown}</span>
                      {rest ? (
                        <span className="opacity-40">{rest}</span>
                      ) : null}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-fd-muted-foreground">
            What you hear
          </p>
          {heard.length === 0 ? (
            <p className="text-sm text-fd-muted-foreground">Silent. Junk turns are not spoken.</p>
          ) : (
            <ol className="space-y-3">
              {heard.map((u, i) => (
                <li key={`${u.text}-${i}`} className="flex gap-3">
                  <span
                    className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                      u.voice === "header"
                        ? "bg-[color-mix(in_oklab,var(--tts-header)_28%,transparent)]"
                        : "bg-[color-mix(in_oklab,var(--tts-accent)_22%,transparent)]"
                    }`}
                  >
                    {u.voice}
                  </span>
                  <blockquote className="m-0 text-sm leading-relaxed">
                    “{u.text}”
                  </blockquote>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
