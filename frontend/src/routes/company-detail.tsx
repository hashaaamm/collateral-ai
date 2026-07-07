import { Link, useParams } from "@tanstack/react-router";
import { CaretRight, Globe } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { useCompany } from "@/lib/api/companies";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-faint">
        {label}
      </div>
      <div className="text-[13.5px] text-body">{value || "—"}</div>
    </div>
  );
}

export function CompanyDetailPage() {
  const { companyId } = useParams({ from: "/app/companies/$companyId" });
  const { data: company, isLoading, isError } = useCompany(Number(companyId));

  if (isLoading) {
    return <div className="mx-auto max-w-[1080px] px-10 pt-8 text-sm text-mute">Loading…</div>;
  }
  if (isError || !company) {
    return (
      <div className="mx-auto max-w-[1080px] px-10 pt-8">
        <p className="text-sm text-destructive">Company not found.</p>
        <Link to="/companies" className="mt-2 inline-block text-sm text-brand">
          Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">
          Companies
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">{company.name}</span>
      </div>

      <div className="mb-6 flex items-center gap-4">
        <CompanyLogo name={company.name} logoUrl={company.logo_url} size={56} />
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">{company.name}</h1>
          <div className="mt-1 flex items-center gap-3">
            {company.industry && (
              <span className="rounded-full bg-brand-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-brand">
                {company.industry}
              </span>
            )}
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-[6px] text-[12.5px] text-subtext hover:text-brand"
              >
                <Globe size={14} />
                {company.website}
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-hairline bg-surface p-6">
        <div className="grid grid-cols-2 gap-6">
          <Field label="Website" value={company.website ?? ""} />
          <Field label="Industry" value={company.industry ?? ""} />
          <div className="col-span-2">
            <Field label="Description" value={company.description ?? ""} />
          </div>
          <div className="col-span-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-faint">
              Brand colors
            </div>
            {company.brand_colors && company.brand_colors.length > 0 ? (
              <div className="flex items-center gap-2">
                {company.brand_colors.map((hex, i) => (
                  <span
                    key={`${hex}-${i}`}
                    title={hex}
                    className="size-[34px] rounded-lg border border-hairline"
                    style={{ background: hex }}
                  />
                ))}
              </div>
            ) : (
              <div className="text-[13.5px] text-body">—</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
