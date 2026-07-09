import { Link } from "@tanstack/react-router";
import {
  Buildings,
  FileText,
  MagicWand,
  Flag,
  CheckCircle,
  CircleNotch,
  ArrowRight,
} from "@phosphor-icons/react";

import { StatCard } from "@/components/stat-card";
import { useDashboardStats } from "@/lib/api/dashboard";
import { useCurrentUser } from "@/lib/api/queries";

/** Dummy recent materials — the materials feature isn't built yet. */
type MaterialStatus = "completed" | "processing" | "needs_review";

const RECENT: Array<{
  title: string;
  sender: string;
  receiver: string;
  status: MaterialStatus;
}> = [
  { title: "AI for Smarter Logistics", sender: "Acme AI", receiver: "DHL Logistics", status: "completed" },
  { title: "Predictive Demand Planning", sender: "Acme AI", receiver: "RetailCo", status: "processing" },
  { title: "Secure AI Infrastructure", sender: "CloudSec", receiver: "Acme AI", status: "needs_review" },
  { title: "Financial Forecasting, Automated", sender: "NordFinance", receiver: "DHL Logistics", status: "completed" },
];

const MATERIAL_PILL: Record<
  MaterialStatus,
  { label: string; cls: string; Icon: typeof CheckCircle; spin?: boolean }
> = {
  completed: { label: "Completed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch, spin: true },
  needs_review: { label: "Needs Review", cls: "text-review bg-review-soft", Icon: Flag },
};

function MaterialPill({ status }: { status: MaterialStatus }) {
  const s = MATERIAL_PILL[status];
  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded-full px-[10px] py-[3px] text-[11.5px] font-semibold ${s.cls}`}
    >
      <s.Icon size={13} weight="fill" className={s.spin ? "animate-spin" : ""} />
      {s.label}
    </span>
  );
}

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function DashboardPage() {
  const { data: user } = useCurrentUser();
  const { data: stats, isLoading } = useDashboardStats();

  const now = new Date();
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
  const firstName = user?.name?.trim().split(/\s+/)[0] || "there";

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      {/* Greeting */}
      <div className="mb-6">
        <div className="text-[13px] text-mute">{dateLabel}</div>
        <h1 className="mt-1 text-[26px] font-bold tracking-[-0.03em] text-ink">
          {greeting(now.getHours())}, {firstName}
        </h1>
      </div>

      {/* Stat grid */}
      <div className="mb-5 grid grid-cols-4 gap-4">
        <StatCard
          label="Companies"
          value={stats?.companies_count ?? 0}
          Icon={Buildings}
          delta="Reusable context"
          tone="muted"
          loading={isLoading}
        />
        <StatCard
          label="Documents processed"
          value={stats?.documents_processed ?? 0}
          Icon={FileText}
          delta={
            stats?.documents_processing
              ? `${stats.documents_processing} processing`
              : "All processed"
          }
          tone="muted"
          loading={isLoading}
        />
        <StatCard
          label="Materials generated"
          value={11}
          Icon={MagicWand}
          delta="+4 this week"
          tone="success"
        />
        <StatCard
          label="Needs review"
          value={2}
          Icon={Flag}
          delta="Awaiting approval"
          tone="warning"
        />
      </div>

      {/* Recent materials + Quick start */}
      <div className="grid grid-cols-[1.6fr_1fr] gap-5">
        {/* Recent materials (dummy) */}
        <div className="rounded-2xl border border-hairline bg-surface p-5">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-ink">Recent materials</h2>
            <Link to="/materials" className="text-[12.5px] text-brand hover:underline">
              View all
            </Link>
          </div>
          <div>
            {RECENT.map((m) => (
              <div
                key={m.title}
                className="flex items-center justify-between rounded-lg px-2 py-[11px] hover:bg-subtle"
              >
                <div>
                  <div className="text-[13px] font-semibold text-ink">{m.title}</div>
                  <div className="text-[11.5px] text-mute">
                    {m.sender} → {m.receiver}
                  </div>
                </div>
                <MaterialPill status={m.status} />
              </div>
            ))}
          </div>
        </div>

        {/* Quick start */}
        <div className="rounded-2xl border border-hairline bg-surface p-5">
          <h2 className="text-[15px] font-semibold text-ink">Quick start</h2>
          <p className="mt-1 text-[13px] text-subtext">
            Generate a tailored marketing article, or manage the company context it draws from.
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <Link
              to="/create"
              className="flex items-center justify-center gap-[7px] rounded-[10px] bg-brand px-[15px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover"
            >
              <MagicWand weight="fill" size={15} />
              Create Material
            </Link>
            <Link
              to="/companies"
              className="flex items-center justify-center gap-[7px] rounded-[10px] border border-field px-[15px] py-[10px] text-[13.5px] font-semibold text-body hover:bg-nav-hover"
            >
              Manage Companies
              <ArrowRight weight="bold" size={14} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
