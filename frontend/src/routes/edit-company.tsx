import { Link, useNavigate, useParams } from "@tanstack/react-router";

import { CompanyForm } from "@/components/company-form";
import { PageSpinner } from "@/components/ui/spinner";
import { useCompany, useUpdateCompany } from "@/lib/api/companies";

export function EditCompanyPage() {
  const { companyId } = useParams({ from: "/app/companies/$companyId/edit" });
  const id = Number(companyId);
  const navigate = useNavigate();
  const { data: company, isLoading, isError } = useCompany(id);
  const update = useUpdateCompany(id);

  if (isLoading) {
    return <PageSpinner />;
  }
  if (isError || !company) {
    return (
      <div className="mx-auto max-w-[760px] px-10 pt-8">
        <p className="text-sm text-destructive">Company not found.</p>
        <Link to="/companies" className="mt-2 inline-block text-sm text-brand">Back to companies</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[760px] px-10 pb-[60px] pt-[26px]">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">Companies</Link>
        <span>/</span>
        <Link to="/companies/$companyId" params={{ companyId }} className="hover:text-brand">{company.name}</Link>
        <span>/</span>
        <span className="font-medium text-body">Edit</span>
      </div>
      <h1 className="mb-[26px] text-[24px] font-bold tracking-[-0.03em] text-ink">Edit company</h1>

      <CompanyForm
        initial={{
          name: company.name,
          website: company.website ?? "",
          industry: company.industry ?? "",
          description: company.description ?? "",
          brand_colors: company.brand_colors ?? [],
          logoUrl: company.logo_url,
        }}
        submitLabel="Save changes"
        submitting={update.isPending}
        error={update.isError}
        cancel={
          <Link to="/companies/$companyId" params={{ companyId }} className="rounded-[10px] border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle">
            Cancel
          </Link>
        }
        onSubmit={(payload) =>
          update.mutate(payload, {
            onSuccess: () => navigate({ to: "/companies/$companyId", params: { companyId } }),
          })
        }
      />
    </div>
  );
}
