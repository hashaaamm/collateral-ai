import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowDownLeft, ArrowUpRight } from "@phosphor-icons/react";

import { StatusPill, materialPillStatus } from "@/components/status-pill";
import { PageSpinner } from "@/components/ui/spinner";
import { useMaterials, type MaterialList } from "@/lib/api/materials";

function MaterialCard({
  material,
  counterpart,
}: {
  material: MaterialList;
  counterpart: string;
}) {
  return (
    <Link
      to="/materials/$materialId"
      params={{ materialId: String(material.id) }}
      className="flex items-center justify-between gap-3 rounded-[11px] border border-hairline p-[13px] hover:border-[#d8d8f2] hover:bg-[#fbfbff]"
    >
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold text-ink">{material.title}</div>
        <div className="mt-[2px] truncate text-[12px] text-subtext">{counterpart}</div>
      </div>
      <StatusPill
        status={materialPillStatus({
          generation_status: material.generation_status ?? "queued",
          review_status: material.review_status ?? "pending",
        })}
      />
    </Link>
  );
}

function Column({
  title,
  tile,
  children,
}: {
  title: string;
  tile: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-[9px]">
        {tile}
        <h3 className="text-[13.5px] font-semibold text-ink">{title}</h3>
      </div>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

export function MaterialsTab({ companyId }: { companyId: number }) {
  const { data: materials, isLoading, isError } = useMaterials({ company: companyId });

  if (isLoading) return <PageSpinner className="min-h-[200px]" />;
  if (isError) return <p className="text-[13px] text-destructive">Failed to load materials.</p>;

  const all = materials ?? [];
  const asSender = all.filter((m) => m.sender_company.id === companyId);
  const asReceiver = all.filter((m) => m.receiver_company.id === companyId);

  return (
    <div className="grid grid-cols-2 gap-6">
      <Column
        title="As Sender"
        tile={
          <span className="flex size-[26px] items-center justify-center rounded-lg bg-brand-soft text-brand">
            <ArrowUpRight size={14} weight="bold" />
          </span>
        }
      >
        {asSender.length === 0 && (
          <p className="text-[12.5px] text-mute">No materials sent by this company yet.</p>
        )}
        {asSender.map((m) => (
          <MaterialCard key={m.id} material={m} counterpart={`→ ${m.receiver_company.name}`} />
        ))}
      </Column>
      <Column
        title="As Receiver"
        tile={
          <span className="flex size-[26px] items-center justify-center rounded-lg bg-review-soft text-review">
            <ArrowDownLeft size={14} weight="bold" />
          </span>
        }
      >
        {asReceiver.length === 0 && (
          <p className="text-[12.5px] text-mute">No materials targeting this company yet.</p>
        )}
        {asReceiver.map((m) => (
          <MaterialCard key={m.id} material={m} counterpart={`${m.sender_company.name} →`} />
        ))}
      </Column>
    </div>
  );
}
