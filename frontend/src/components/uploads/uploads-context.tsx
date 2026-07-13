import { useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { uploadDocument } from "@/lib/api/documents";
import { UploadsContext, type UploadItem } from "@/components/uploads/use-uploads";

const AUTO_DISMISS_MS = 5000;

function uploadErrorMessage(e: unknown) {
  return e instanceof Error && e.message === "upload_not_configured"
    ? "Document upload isn't configured in this environment."
    : "Upload failed. Try again.";
}

export function UploadsProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearTimer() {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function patch(id: string, p: Partial<UploadItem>) {
    setItems((prev) => prev.map((u) => (u.id === id ? { ...u, ...p } : u)));
  }

  function dismiss() {
    clearTimer();
    setItems([]);
  }

  async function runOne(item: UploadItem, file: File) {
    try {
      await uploadDocument({
        companyId: item.companyId,
        file,
        onProgress: (pct) =>
          patch(item.id, {
            progress: pct,
            // Bytes uploaded; the /complete call is now in flight.
            ...(pct >= 100 ? { status: "processing" } : null),
          }),
      });
      patch(item.id, { status: "done", progress: 100 });
      // Per-file refetch so each finished doc appears promptly, rather than
      // waiting for the whole batch to settle.
      qc.invalidateQueries({ queryKey: ["documents", item.companyId] });
    } catch (e) {
      patch(item.id, { status: "error", error: uploadErrorMessage(e) });
    }
  }

  function maybeScheduleDismiss(current: UploadItem[]) {
    const allSettled = current.every(
      (u) => u.status === "done" || u.status === "error",
    );
    const anyError = current.some((u) => u.status === "error");
    if (allSettled && !anyError) {
      clearTimer();
      timerRef.current = setTimeout(() => {
        dismiss();
      }, AUTO_DISMISS_MS);
    }
  }

  function enqueue(files: FileList | File[], companyId: number) {
    clearTimer();
    const selected = Array.from(files);
    const newItems: UploadItem[] = selected.map((file) =>
      file.type === "application/pdf"
        ? {
            id: crypto.randomUUID(),
            name: file.name,
            companyId,
            status: "uploading",
            progress: 0,
          }
        : {
            id: crypto.randomUUID(),
            name: file.name,
            companyId,
            status: "error",
            progress: 0,
            error: "Only PDF files are supported.",
          },
    );
    setItems((prev) => [...prev, ...newItems]);

    const runnable = newItems.flatMap((item, i) =>
      item.status === "uploading" ? [{ item, file: selected[i] }] : [],
    );

    const settle = () =>
      // Re-read the freshest items via the state updater to decide auto-dismiss.
      setItems((prev) => {
        maybeScheduleDismiss(prev);
        return prev;
      });

    if (runnable.length === 0) {
      settle();
      return;
    }

    Promise.allSettled(runnable.map(({ item, file }) => runOne(item, file))).then(settle);
  }

  return (
    <UploadsContext.Provider value={{ items, enqueue, dismiss }}>
      {children}
    </UploadsContext.Provider>
  );
}
