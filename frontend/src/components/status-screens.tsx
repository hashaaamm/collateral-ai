import { type ReactNode } from "react";
import {
  Link,
  useRouter,
  type ErrorComponentProps,
} from "@tanstack/react-router";
import {
  ArrowClockwise,
  ArrowLeft,
  Buildings,
  Layout,
  ListChecks,
  MagicWand,
  SquaresFour,
  Stack,
  Warning,
} from "@phosphor-icons/react";

import { isAuthenticated } from "@/lib/auth";

// Shared button treatments, matched to the app's primary/ghost buttons.
const PRIMARY =
  "inline-flex items-center justify-center gap-2 rounded-[10px] bg-brand px-[18px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover";
const GHOST =
  "inline-flex items-center justify-center gap-2 rounded-[10px] border border-field bg-surface px-[18px] py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle";

/**
 * The shared status surface. `full` centers a card on the login radial for
 * chrome-less contexts (top-level 404, errors before the shell mounts).
 * `inline` centers within AppShell's main so the sidebar stays put.
 */
function StatusCard({
  variant,
  children,
}: {
  variant: "full" | "inline";
  children: ReactNode;
}) {
  const card = (
    <div className="w-full max-w-[440px] rounded-2xl border border-hairline bg-surface p-9 text-center shadow-login [animation:heroUp_.5s_cubic-bezier(.2,.7,.2,1)_both] motion-reduce:animate-none">
      {children}
    </div>
  );
  if (variant === "inline") {
    return (
      <div className="flex min-h-full items-center justify-center p-10">
        {card}
      </div>
    );
  }
  return (
    <div className="flex min-h-dvh items-center justify-center bg-[radial-gradient(120%_120%_at_50%_0%,#eeeefb_0%,#f6f6f8_55%)] p-6">
      {card}
    </div>
  );
}

function Mark({ tone }: { tone: "brand" | "warning" }) {
  if (tone === "warning") {
    return (
      <div className="mx-auto mb-5 flex size-[42px] items-center justify-center rounded-[12px] bg-warning-soft">
        <Warning weight="fill" size={22} className="text-warning" />
      </div>
    );
  }
  return (
    <div className="mx-auto mb-5 flex size-[42px] items-center justify-center rounded-[12px] bg-brand shadow-[0_4px_12px_rgba(91,91,214,0.35)]">
      <Stack weight="fill" size={22} className="text-white" />
    </div>
  );
}

function Title({ children }: { children: ReactNode }) {
  return (
    <h1 className="text-[19px] font-bold tracking-[-0.02em] text-ink">
      {children}
    </h1>
  );
}

function Description({ children }: { children: ReactNode }) {
  return (
    <p className="mx-auto mt-2 max-w-[340px] text-[13.5px] leading-[1.55] text-subtext">
      {children}
    </p>
  );
}

// The workspace destinations, mirroring the sidebar — turns the 404 from a dead
// end into an invitation to act.
const QUICK_LINKS = [
  { to: "/dashboard", label: "Dashboard", Icon: SquaresFour },
  { to: "/companies", label: "Companies", Icon: Buildings },
  { to: "/create", label: "Create", Icon: MagicWand },
  { to: "/materials", label: "Requests", Icon: ListChecks },
  { to: "/templates", label: "Templates", Icon: Layout },
] as const;

/**
 * Chrome-less 404. Renders the attempted path as one of the app's own mono
 * "slug" chips, marked unresolved — a URL is an identifier that didn't resolve
 * to a resource, exactly like the template slugs shown elsewhere.
 */
export function NotFoundScreen() {
  const authed = isAuthenticated();
  const path = typeof window !== "undefined" ? window.location.pathname : "";

  return (
    <StatusCard variant="full">
      <Mark tone="brand" />
      {path && (
        <div className="mx-auto mb-5 inline-flex max-w-full items-center gap-2 rounded-full border border-hairline bg-subtle px-3 py-[5px] font-mono text-[12px] text-mute">
          <span className="truncate">{path}</span>
          <span className="flex-none rounded-full bg-danger-soft px-[7px] py-[1px] text-[10px] font-semibold text-destructive">
            not found
          </span>
        </div>
      )}
      <Title>Page not found</Title>
      <Description>
        We couldn&rsquo;t find a page at that address. It may have moved, or the
        link was mistyped.
      </Description>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {authed ? (
          <Link to="/dashboard" className={PRIMARY}>
            <ArrowLeft weight="bold" size={15} />
            Back to dashboard
          </Link>
        ) : (
          <>
            <Link to="/" className={PRIMARY}>
              Go to homepage
            </Link>
            <Link to="/login" className={GHOST}>
              Sign in
            </Link>
          </>
        )}
      </div>

      {authed && (
        <div className="mt-7 border-t border-hairline pt-5">
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.05em] text-faint">
            Jump to
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {QUICK_LINKS.map(({ to, label, Icon }) => (
              <Link
                key={to}
                to={to}
                className="inline-flex items-center gap-[7px] rounded-full border border-hairline bg-surface px-[13px] py-[7px] text-[12.5px] font-medium text-body hover:bg-nav-hover"
              >
                <Icon size={15} className="text-mute" />
                {label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </StatusCard>
  );
}

function ErrorScreen({
  variant,
  error,
  reset,
}: {
  variant: "full" | "inline";
  error?: Error;
  reset: () => void;
}) {
  const router = useRouter();
  return (
    <StatusCard variant={variant}>
      <Mark tone="warning" />
      <Title>Something went wrong</Title>
      <Description>
        This page ran into an unexpected error. You can try again, or head back
        to your dashboard.
      </Description>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={() => {
            reset();
            router.invalidate();
          }}
          className={PRIMARY}
        >
          <ArrowClockwise weight="bold" size={15} />
          Try again
        </button>
        <Link to="/dashboard" className={GHOST}>
          Back to dashboard
        </Link>
      </div>

      {import.meta.env.DEV && error && (
        <details className="mt-6 text-left">
          <summary className="cursor-pointer text-[12px] font-semibold text-mute">
            Error details (dev only)
          </summary>
          <pre className="mt-2 max-h-[200px] overflow-auto rounded-lg bg-subtle p-3 font-mono text-[11px] leading-relaxed text-body">
            {error.message}
            {error.stack ? `\n\n${error.stack}` : ""}
          </pre>
        </details>
      )}
    </StatusCard>
  );
}

/** Router-level catch-all: errors above the shell, or before it mounts. */
export function RootErrorScreen({ error, reset }: ErrorComponentProps) {
  return <ErrorScreen variant="full" error={error} reset={reset} />;
}

/** In-shell fallback (via ErrorBoundary in AppShell) — keeps the sidebar. */
export function InShellErrorScreen({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return <ErrorScreen variant="inline" error={error} reset={reset} />;
}
