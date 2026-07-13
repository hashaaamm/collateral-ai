import { useState } from "react";
import { CaretDown, CaretUp, FilePdf, X } from "@phosphor-icons/react";

import { useUploads, type UploadItem } from "@/components/uploads/use-uploads";

function summaryLabel(items: UploadItem[]) {
  const total = items.length;
  const inFlight = items.filter(
    (u) => u.status === "uploading" || u.status === "processing",
  ).length;
  if (inFlight > 0) {
    const done = items.filter((u) => u.status === "done").length;
    return `Uploading ${done} of ${total}`;
  }
  const failed = items.filter((u) => u.status === "error").length;
  if (failed > 0) return `${failed} failed`;
  return "Uploads complete";
}

export function UploadTray() {
  const { items, dismiss } = useUploads();
  const [collapsed, setCollapsed] = useState(false);

  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[60] w-[360px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-hairline bg-surface shadow-lg">
      <div className="flex items-center justify-between gap-2 border-b border-hairline-soft bg-subtle px-4 py-[10px]">
        <span className="truncate text-[12.5px] font-semibold text-body">
          {summaryLabel(items)}
        </span>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-faint hover:bg-hairline-soft hover:text-body"
            aria-label={collapsed ? "Expand uploads" : "Collapse uploads"}
          >
            {collapsed ? <CaretUp size={15} /> : <CaretDown size={15} />}
          </button>
          <button
            type="button"
            onClick={() => dismiss()}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-faint hover:bg-hairline-soft hover:text-body"
            aria-label="Close uploads"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {!collapsed && (
        <ul className="flex max-h-[280px] flex-col gap-[10px] overflow-y-auto px-4 py-3">
          {items.map((u) => (
            <li key={u.id} className="flex flex-col gap-[6px]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-[9px]">
                  <FilePdf size={16} className="shrink-0 text-destructive" />
                  <span className="truncate text-[12.5px] font-medium text-body">{u.name}</span>
                </div>
                {(u.status === "done" || u.status === "error") && (
                  <span
                    className={`shrink-0 text-[11.5px] ${
                      u.status === "error" ? "text-destructive" : "text-faint"
                    }`}
                  >
                    {u.status === "done" ? "done" : `failed — ${u.error}`}
                  </span>
                )}
              </div>
              {(u.status === "uploading" || u.status === "processing") && (
                <div className="h-[6px] w-full overflow-hidden rounded-full bg-hairline-soft">
                  <div
                    className="h-full bg-brand transition-[width]"
                    style={{ width: `${u.progress}%` }}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
