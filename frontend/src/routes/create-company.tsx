import { Link, useNavigate } from "@tanstack/react-router";

import { CompanyForm } from "@/components/company-form";
import { useCreateCompany } from "@/lib/api/companies";

export function CreateCompanyPage() {
  const navigate = useNavigate();
  const create = useCreateCompany();

  return (
    <div className="mx-auto max-w-[760px] px-10 pb-[60px] pt-[26px]">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">Companies</Link>
        <span>/</span>
        <span className="font-medium text-body">New company</span>
      </div>
      <h1 className="mb-1 text-[24px] font-bold tracking-[-0.03em] text-ink">Create Company</h1>
      <p className="mb-[26px] text-[13.5px] text-subtext">Add a company profile.</p>

      <CompanyForm
        submitLabel="Create Company"
        submitting={create.isPending}
        error={create.isError}
        cancel={
          <Link to="/companies" className="rounded-[10px] border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle">
            Cancel
          </Link>
        }
        onSubmit={(payload) =>
          create.mutate(
            { ...payload, name: payload.name },
            { onSuccess: (c) => navigate({ to: "/companies/$companyId", params: { companyId: String(c.id) } }) },
          )
        }
      />
    </div>
  );
}
