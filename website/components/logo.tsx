import Image from "next/image";

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-[family-name:var(--font-display)] text-[15px] font-semibold tracking-tight">
      <Image
        src="/logo.png"
        alt=""
        width={24}
        height={24}
        className="h-6 w-6 rounded-md"
        priority
      />
      agent-tts
    </span>
  );
}
