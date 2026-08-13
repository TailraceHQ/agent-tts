export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-[family-name:var(--font-display)] text-[15px] font-semibold tracking-tight">
      <span
        aria-hidden
        className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-[var(--tts-accent)] text-[11px] text-[var(--tts-accent-fg)]"
      >
        ▶
      </span>
      agent-tts
    </span>
  );
}
