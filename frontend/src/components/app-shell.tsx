import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Buildings,
  Layout,
  ListChecks,
  MagicWand,
  SignOut,
  SquaresFour,
  Stack,
} from "@phosphor-icons/react";

import { useCurrentUser } from "@/lib/api/queries";
import { clearToken } from "@/lib/auth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", Icon: SquaresFour },
  { to: "/companies", label: "Companies", Icon: Buildings },
  { to: "/create", label: "Create Material", Icon: MagicWand },
  { to: "/materials", label: "Marketing Requests", Icon: ListChecks },
  { to: "/templates", label: "Templates", Icon: Layout },
] as const;

const NAV_BASE =
  "flex items-center gap-[11px] rounded-[9px] px-[10px] py-[9px] text-[13.5px] font-medium";

function initials(name: string | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function AppShell() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const displayName = user?.name?.trim() ? user.name : "Account";

  function signOut() {
    queryClient.clear();
    clearToken();
    navigate({ to: "/login" });
  }

  return (
    <div className="flex min-h-dvh bg-page text-ink">
      <aside className="sticky top-0 flex h-dvh w-[236px] flex-none flex-col border-r border-hairline bg-surface">
        {/* Brand */}
        <div className="flex items-center gap-[10px] px-[18px] pb-[14px] pt-[18px]">
          <div className="flex size-[30px] items-center justify-center rounded-lg bg-brand">
            <Stack weight="fill" size={17} className="text-white" />
          </div>
          <span className="text-base font-bold tracking-[-0.02em]">
            Collateral AI
          </span>
          <span className="ml-auto rounded-[5px] border border-hairline px-[5px] py-[2px] text-[9.5px] font-semibold text-mute">
            MVP
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-[2px] px-3 py-[6px]">
          <div className="px-[10px] pb-[5px] pt-[10px] text-[10.5px] font-semibold uppercase tracking-[0.05em] text-faint">
            Workspace
          </div>
          {NAV.map(({ to, label, Icon }) => (
            // TanStack Router concatenates className with active/inactiveProps
            // className, so keep only shared classes here and only the
            // differing (state-specific) classes in the props below.
            <Link
              key={to}
              to={to}
              className={NAV_BASE}
              inactiveProps={{ className: "text-nav hover:bg-nav-hover" }}
              activeProps={{ className: "bg-brand-soft text-ink" }}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        {/* User card */}
        <div className="mt-auto p-3">
          <div className="rounded-xl border border-hairline-soft bg-rail p-3">
            <div className="flex items-center gap-[9px]">
              <div className="flex size-[30px] items-center justify-center rounded-lg bg-brand-tint text-[13px] font-bold text-brand">
                {initials(user?.name)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold">
                  {displayName}
                </div>
                <div className="text-[11px] text-mute">Editor</div>
              </div>
              <button
                type="button"
                onClick={signOut}
                title="Sign out"
                aria-label="Sign out"
                className="ml-auto text-mute hover:text-brand"
              >
                <SignOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="h-dvh flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
