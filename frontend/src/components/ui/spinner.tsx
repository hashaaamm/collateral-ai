import { CircleNotch } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

function Spinner({ size, className }: { size?: number; className?: string }) {
  return (
    <CircleNotch
      weight="bold"
      size={size ?? 16}
      className={cn("animate-spin", className)}
    />
  );
}

function LoadingState({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-2 text-mute", className)}>
      <Spinner />
      <span className="text-[13px]">{label ?? "Loading…"}</span>
    </div>
  );
}

export { Spinner, LoadingState };
