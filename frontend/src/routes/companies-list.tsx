import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Buildings, CaretRight, MagnifyingGlass, Plus } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { PageSpinner } from "@/components/ui/spinner";
import { useCompanies } from "@/lib/api/companies";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { formatRelativeDay } from "@/lib/format";

export function CompaniesListPage() {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const { data: companies, isLoading, isError } = useCompanies(debounced);

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.03em] text-ink">Companies</h1>
          <p className="mt-1 text-sm text-subtext">
            Reusable company context shared across every generation.
          </p>
        </div>
        <Link
          to="/companies/new"
          className="flex items-center gap-[7px] rounded-[10px] bg-brand px-[15px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus weight="bold" size={14} />
          Create Company
        </Link>
      </div>

      <div className="mb-4 flex items-center gap-[9px] rounded-[10px] border border-field bg-surface px-3">
        <MagnifyingGlass size={16} className="text-faint" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies…"
          aria-label="Search companies"
          className="w-full bg-transparent py-[10px] text-[13.5px] text-ink outline-none placeholder:text-faint"
        />
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 border-b border-hairline bg-subtle px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <span>Company</span>
          <span>Industry</span>
          <span>Website</span>
          <span>Last updated</span>
          <span className="w-4" />
        </div>

        {isLoading && <PageSpinner className="min-h-[200px]" />}
        {isError && (
          <div className="px-5 py-8 text-center text-sm text-destructive">
            Couldn't load companies.
          </div>
        )}
        {companies?.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-5 py-12 text-center">
            <Buildings size={28} className="text-faint" />
            <p className="text-sm text-mute">
              {debounced.trim() ? `No companies match "${debounced.trim()}".` : "No companies yet."}
            </p>
          </div>
        )}
        {companies?.map((c) => (
          <Link
            key={c.id}
            to="/companies/$companyId"
            params={{ companyId: String(c.id) }}
            className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] items-center gap-4 border-b border-hairline px-5 py-[14px] last:border-b-0 hover:bg-subtle"
          >
            <span className="flex items-center gap-3">
              <CompanyLogo name={c.name} logoUrl={c.logo_url} />
              <span className="text-[13.5px] font-semibold text-ink">{c.name}</span>
            </span>
            <span className="text-[13px] text-body">
              {c.industry ? (
                <span className="rounded-full bg-brand-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-brand">
                  {c.industry}
                </span>
              ) : (
                "—"
              )}
            </span>
            <span className="truncate text-[13px] text-subtext">{c.website || "—"}</span>
            <span className="text-[13px] text-subtext">{formatRelativeDay(c.last_updated)}</span>
            <CaretRight size={14} className="text-faint" />
          </Link>
        ))}
      </div>
    </div>
  );
}
