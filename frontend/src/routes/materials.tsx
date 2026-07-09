import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { MagnifyingGlass, Plus } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { StatusPill, materialPillStatus } from "@/components/status-pill";
import { useMaterials, type MaterialList } from "@/lib/api/materials";
import { useDebouncedValue } from "@/lib/use-debounced-value";

// Chip set is derived-pill based — deliberate deviation from the design's chips,
// which predate the review workflow (spec §7.3).
const CHIPS = [
  ["all", "All"],
  ["needs_review", "Needs review"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
  ["processing", "Processing"],
  ["failed", "Failed"],
] as const;
type Chip = (typeof CHIPS)[number][0];

export function MaterialsPage() {
  const [search, setSearch] = useState("");
  const [chip, setChip] = useState<Chip>("all");
  const debounced = useDebouncedValue(search, 300);
  const { data: materials, isLoading } = useMaterials(
    debounced.trim() ? { search: debounced.trim() } : {},
  );
  const navigate = useNavigate();

  const all = materials ?? [];
  const count = (c: Chip) =>
    c === "all"
      ? all.length
      : all.filter(
          (m) =>
            materialPillStatus({
              generation_status: m.generation_status ?? "queued",
              review_status: m.review_status ?? "pending",
            }) === c,
        ).length;
  const rows =
    chip === "all"
      ? all
      : all.filter(
          (m) =>
            materialPillStatus({
              generation_status: m.generation_status ?? "queued",
              review_status: m.review_status ?? "pending",
            }) === chip,
        );

  const companyCell = (company: MaterialList["sender_company"]) => (
    <span className="flex items-center gap-2">
      <CompanyLogo name={company.name} logoUrl={company.logo_url} size={24} />
      <span className="truncate text-[13px] text-body">{company.name}</span>
    </span>
  );

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-center">
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">
            Marketing Requests
          </h1>
          <p className="mt-1 text-[13px] text-subtext">
            Every generation request across companies.
          </p>
        </div>
        <Link
          to="/create"
          className="ml-auto flex items-center gap-[7px] rounded-[10px] bg-brand px-[14px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus size={15} weight="bold" />
          New Request
        </Link>
      </div>

      <div className="mb-4 flex items-center gap-2">
        {CHIPS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setChip(value)}
            className={`rounded-full px-[12px] py-[5px] text-[12px] font-semibold ${
              chip === value
                ? "bg-ink text-white"
                : "border border-hairline bg-surface text-subtext hover:text-body"
            }`}
          >
            {label} {count(value)}
          </button>
        ))}
        <div className="relative ml-auto">
          <MagnifyingGlass
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-mute"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles…"
            className="w-[220px] rounded-[10px] border border-field bg-subtle py-[8px] pl-8 pr-3 text-[13px] text-body outline-none focus:border-brand"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-hairline text-[11px] font-semibold uppercase tracking-wide text-faint">
              <th className="px-5 py-3">Title</th>
              <th className="px-5 py-3">Sender</th>
              <th className="px-5 py-3">Receiver</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-[13px] text-mute">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-[13px] text-mute">
                  No requests yet — create one to get started.
                </td>
              </tr>
            )}
            {rows.map((m) => (
              <tr
                key={m.id}
                onClick={() =>
                  navigate({
                    to: "/materials/$materialId",
                    params: { materialId: String(m.id) },
                  })
                }
                className="cursor-pointer border-b border-hairline last:border-0 hover:bg-[#fafafb]"
              >
                <td className="px-5 py-3 text-[13px] font-semibold text-ink">{m.title}</td>
                <td className="px-5 py-3">{companyCell(m.sender_company)}</td>
                <td className="px-5 py-3">{companyCell(m.receiver_company)}</td>
                <td className="px-5 py-3">
                  <StatusPill
                    status={materialPillStatus({
                      generation_status: m.generation_status ?? "queued",
                      review_status: m.review_status ?? "pending",
                    })}
                  />
                </td>
                <td className="px-5 py-3 text-[12.5px] text-subtext">
                  {new Date(m.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
