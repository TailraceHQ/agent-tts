export type SpeakMode = "summary" | "closing" | "brief" | "full";
export type SpeakVoice = "header" | "prose";
export type BlockKind = "heading" | "paragraph" | "code" | "blockquote";

export type DemoBlock = {
  id: string;
  kind: BlockKind;
  voice: SpeakVoice;
  label: string;
  text: string;
  /** First sentence, when brief slices this block. */
  brief?: string;
};

export const SAMPLE_TURN: DemoBlock[] = [
  {
    id: "title",
    kind: "heading",
    voice: "header",
    label: "Heading",
    text: "Fix the Stop hook timeout",
  },
  {
    id: "preamble",
    kind: "paragraph",
    voice: "prose",
    label: "Lead paragraph",
    text: "I'll check the Cursor adapter and the shared runner. Then I'll raise the timeout and add a test.",
    brief: "I'll check the Cursor adapter and the shared runner.",
  },
  {
    id: "body",
    kind: "paragraph",
    voice: "prose",
    label: "Body",
    text: "The stop hook currently times out at 10 seconds, which is enough to notify the daemon but not to wait on playback. I raised it in hosts/cursor/hooks.json and documented why.",
  },
  {
    id: "quote",
    kind: "blockquote",
    voice: "header",
    label: "Blockquote",
    text: "Keep the hook fail-open. A TTS failure must never block the turn.",
  },
  {
    id: "code",
    kind: "code",
    voice: "prose",
    label: "Code block",
    text: "see codeblock below",
  },
  {
    id: "closing",
    kind: "paragraph",
    voice: "prose",
    label: "Closing paragraph",
    text: "The tests are green. Bind skip to a hotkey next.",
  },
];

export function spokenIds(mode: SpeakMode): Set<string> {
  switch (mode) {
    case "summary":
      return new Set(["preamble"]);
    case "brief":
      return new Set(["preamble"]);
    case "closing":
      return new Set(["closing"]);
    case "full":
      return new Set(SAMPLE_TURN.map((b) => b.id));
  }
}

export function heardText(mode: SpeakMode): { voice: SpeakVoice; text: string }[] {
  const ids = spokenIds(mode);
  const out: { voice: SpeakVoice; text: string }[] = [];
  for (const block of SAMPLE_TURN) {
    if (!ids.has(block.id)) continue;
    if (mode === "brief" && block.brief) {
      out.push({ voice: block.voice, text: block.brief });
    } else {
      out.push({ voice: block.voice, text: block.text });
    }
  }
  return out;
}
