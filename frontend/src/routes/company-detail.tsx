import { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { CaretRight, Globe, PencilSimple, Trash } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { DocumentsTab } from "@/components/documents-tab";
import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
import { useCompany, useDeleteCompany } from "@/lib/api/companies";

const TABS = ["Overview", "Documents", "Generated Materials"] as const;
type Tab = (typeof TABS)[number];

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
  const navigate = useNavigate();
  const del = useDeleteCompany();
  const [tab, setTab] = useState<Tab>("Overview");
  const [deleteOpen, setDeleteOpen] = useState(false);

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
        <div className="ml-auto flex items-center gap-[9px]">
          <Link
            to="/companies/$companyId/edit"
            params={{ companyId: String(company.id) }}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle"
          >
            <PencilSimple size={15} />
            Edit
          </Link>
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle"
          >
            <Trash size={15} />
            Delete
          </button>
        </div>
      </div>

      <div className="mb-5 flex gap-5 border-b border-hairline">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 pb-[10px] text-[13.5px] font-medium ${
              tab === t ? "border-brand text-ink" : "border-transparent text-mute hover:text-body"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && (
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
      )}
      {tab === "Documents" && <DocumentsTab companyId={Number(companyId)} />}
      {tab === "Generated Materials" && (
        <p className="text-[13px] text-mute">Coming soon.</p>
      )}

      <ConfirmDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${company.name}?`}
        description={
          <>
            This permanently removes the company and its logo. This can&apos;t be undone.
          </>
        }
        loading={del.isPending}
        onConfirm={() =>
          del.mutate(company.id, {
            onSuccess: () => {
              setDeleteOpen(false);
              navigate({ to: "/companies" });
            },
          })
        }
      />
    </div>
  );
}
