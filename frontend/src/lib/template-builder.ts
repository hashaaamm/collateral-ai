import type { TemplateImageSlot } from "@/lib/api/templates";

export function slugifyId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** slot_id per row: slugified label, uniquified with _2, _3… (spec §7.3). */
export function toImageSlots(
  rows: { label: string; spec: string; source: TemplateImageSlot["source"] }[],
): TemplateImageSlot[] {
  const seen = new Map<string, number>();
  return rows.map((row) => {
    const base = slugifyId(row.label) || "slot";
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    return { slot_id: n === 1 ? base : `${base}_${n}`, ...row };
  });
}
