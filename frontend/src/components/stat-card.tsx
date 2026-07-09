import type { Icon } from "@phosphor-icons/react";

const TONE: Record<string, string> = {
  success: "text-success",
  warning: "text-warning",
  muted: "text-mute",
};

export function StatCard({
  label,
  value,
  Icon,
  delta,
  tone = "muted",
  loading = false,
}: {
  label: string;
  value: number | string;
  Icon: Icon;
  delta?: string;
  tone?: "success" | "warning" | "muted";
  loading?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-[18px]">
      <div className="flex items-start justify-between">
        <span className="text-[12.5px] text-subtext">{label}</span>
        <Icon size={18} weight="regular" className="text-faint" />
      </div>
      {loading ? (
        <div className="mt-2 h-[27px] w-12 animate-pulse rounded bg-subtle" />
      ) : (
        <div className="mt-2 text-[27px] font-bold leading-none text-ink">{value}</div>
      )}
      {/* Render an empty spacer (&nbsp;) when there's no delta so every card in the
          grid keeps the same height as those with a caption line. */}
      <div className={`mt-[7px] text-[12px] ${loading ? "text-faint" : TONE[tone]}`}>
        {loading ? "—" : (delta ?? " ")}
      </div>
    </div>
  );
}
