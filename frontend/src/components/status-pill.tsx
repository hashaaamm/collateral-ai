import { CheckCircle, CircleNotch, Flag, Prohibit, XCircle } from "@phosphor-icons/react";

const MAP: Record<string, { label: string; cls: string; Icon: typeof CheckCircle }> = {
  processed: { label: "Processed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  pending: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  failed: { label: "Failed", cls: "text-destructive bg-danger-soft", Icon: XCircle },
  needs_review: { label: "Needs review", cls: "text-review bg-review-soft", Icon: Flag },
  approved: { label: "Approved", cls: "text-success bg-success-soft", Icon: CheckCircle },
  rejected: { label: "Rejected", cls: "text-destructive bg-danger-soft", Icon: Prohibit },
};

/** Derived pill for materials (spec §3.2): two status fields → one pill. */
export function materialPillStatus(m: {
  generation_status: string;
  review_status: string;
}): "processing" | "failed" | "needs_review" | "approved" | "rejected" {
  if (m.generation_status === "failed") return "failed";
  if (m.generation_status !== "completed") return "processing";
  if (m.review_status === "approved") return "approved";
  if (m.review_status === "rejected") return "rejected";
  return "needs_review";
}

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
