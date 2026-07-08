import { CheckCircle, CircleNotch, XCircle } from "@phosphor-icons/react";

const MAP: Record<string, { label: string; cls: string; Icon: typeof CheckCircle }> = {
  processed: { label: "Processed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  pending: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  failed: { label: "Failed", cls: "text-destructive bg-danger-soft", Icon: XCircle },
};

export function StatusPill({ status }: { status: string }) {
  const s = MAP[status] ?? MAP.pending;
  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded-full px-[10px] py-[3px] text-[11.5px] font-semibold ${s.cls}`}
    >
      <s.Icon size={13} weight="fill" className={status === "processing" ? "animate-spin" : ""} />
      {s.label}
    </span>
  );
}
