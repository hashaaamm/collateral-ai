import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowClockwise, ArrowSquareOut, FilePdf, Trash, UploadSimple } from "@phosphor-icons/react";

import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
import { StatusPill } from "@/components/status-pill";
import { LoadingState } from "@/components/ui/spinner";
import {
  fetchDocumentViewUrl,
  useCompleteDocument,
  useDeleteDocument,
  useDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api/documents";

function num(n: number | null | undefined) {
  return n == null ? "—" : String(n);
}

type UploadStatus = "uploading" | "processing" | "done" | "error";

type UploadItem = {
  id: string;
  name: string;
  status: UploadStatus;
  progress: number;
  error?: string;
};

function uploadErrorMessage(e: unknown) {
  return e instanceof Error && e.message === "upload_not_configured"
    ? "Document upload isn't configured in this environment."
    : "Upload failed. Try again.";
}

export function DocumentsTab({ companyId }: { companyId: number }) {
  const qc = useQueryClient();
  const { data: docs = [], isLoading } = useDocuments(companyId);
  const retry = useCompleteDocument();
  const del = useDeleteDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [openError, setOpenError] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);

  function patchUpload(id: string, patch: Partial<UploadItem>) {
    setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...patch } : u)));
  }

  async function onOpen(d: Document) {
    setOpenError("");
    setOpeningId(d.id);
    // Open the tab synchronously (before the await) so the browser doesn't treat
    // it as a popup. Note: passing "noopener" to window.open makes it return null,
    // so we keep the handle and null `opener` ourselves before navigating.
    const w = window.open("", "_blank");
    if (!w) {
      setOpenError("Couldn't open the document. Allow pop-ups and try again.");
      setOpeningId(null);
      return;
    }
    try {
      const url = await fetchDocumentViewUrl(companyId, d.id);
      w.opener = null;
      w.location.href = url;
    } catch {
      w.close();
      setOpenError("Couldn't open the document. Try again.");
    } finally {
      setOpeningId(null);
    }
  }

  async function runOne(item: UploadItem, file: File) {
    try {
      await uploadDocument({
        companyId,
        file,
        onProgress: (pct) =>
          patchUpload(item.id, {
            progress: pct,
            // Bytes uploaded; the /complete call is now in flight.
            ...(pct >= 100 ? { status: "processing" } : null),
          }),
      });
      patchUpload(item.id, { status: "done", progress: 100 });
    } catch (e) {
      patchUpload(item.id, { status: "error", error: uploadErrorMessage(e) });
    }
  }

  async function onFiles(files: FileList | null) {
    if (!files) return;
    const selected = Array.from(files);
    const items: UploadItem[] = selected.map((file) =>
      file.type === "application/pdf"
        ? { id: crypto.randomUUID(), name: file.name, status: "uploading", progress: 0 }
        : {
            id: crypto.randomUUID(),
            name: file.name,
            status: "error",
            progress: 0,
            error: "Only PDF files are supported.",
          },
    );
    setUploads(items);

    const runnable = items.flatMap((item, i) =>
      item.status === "uploading" ? [runOne(item, selected[i])] : [],
    );
    if (runnable.length === 0) return;

    await Promise.allSettled(runnable);
    qc.invalidateQueries({ queryKey: ["documents", companyId] });
  }

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        multiple
        hidden
        aria-label="Upload PDF documents"
        onChange={(e) => onFiles(e.target.files)}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        className="mb-4 flex w-full flex-col items-center gap-2 rounded-2xl border border-dashed border-field bg-subtle py-8 text-center hover:bg-surface"
      >
        <UploadSimple size={22} className="text-faint" />
        <span className="text-[13.5px] font-medium text-body">
          Drop PDFs here or <span className="text-brand">browse</span>
        </span>
        <span className="text-[11.5px] text-faint">PDF only · max 50 MB</span>
      </button>

      {uploads.length > 0 && (
        <ul className="mb-4 flex flex-col gap-2">
          {uploads.map((u) => (
            <li key={u.id} className="flex flex-col gap-[6px]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-[9px]">
                  <FilePdf size={16} className="shrink-0 text-destructive" />
                  <span className="truncate text-[12.5px] font-medium text-body">{u.name}</span>
                </div>
                <span
                  className={`shrink-0 text-[11.5px] ${
                    u.status === "error" ? "text-destructive" : "text-faint"
                  }`}
                >
                  {u.status === "uploading" && `uploading ${u.progress}%`}
                  {u.status === "processing" && "processing"}
                  {u.status === "done" && "done"}
                  {u.status === "error" && `failed — ${u.error}`}
                </span>
              </div>
              {u.status !== "error" && (
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
      {openError && <p className="mb-3 text-[12.5px] text-destructive">{openError}</p>}

      {isLoading ? (
        <LoadingState />
      ) : docs.length === 0 ? (
        <p className="text-[13px] text-mute">No documents yet. Upload a PDF to get started.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
          <table className="w-full text-[13px]">
            <thead className="bg-subtle text-[11px] font-semibold uppercase tracking-wide text-faint">
              <tr>
                <th className="px-4 py-[10px] text-left">File name</th>
                <th className="px-4 py-[10px] text-center">Pages</th>
                <th className="px-4 py-[10px] text-center">Chunks</th>
                <th className="px-4 py-[10px] text-center">Tables</th>
                <th className="px-4 py-[10px] text-center">Images</th>
                <th className="px-4 py-[10px] text-left">Status</th>
                <th className="w-[76px] px-4 py-[10px]"></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d: Document) => (
                <tr key={d.id} className="border-t border-hairline-soft">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-[9px]">
                      <FilePdf size={18} className="text-destructive" />
                      <span className="font-medium text-body">{d.file_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.page_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.chunks_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.tables_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.images_count)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <StatusPill status={d.status} />
                      {d.status === "failed" && (
                        <button
                          type="button"
                          onClick={() => retry.mutate({ id: d.id, companyId })}
                          className="flex items-center gap-1 text-[12px] text-brand hover:underline"
                        >
                          <ArrowClockwise size={13} /> Retry
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {/* Every listed doc has a storage object (set at create time), so Open is always shown. */}
                      <button
                        type="button"
                        disabled={openingId === d.id}
                        onClick={() => onOpen(d)}
                        className="flex h-[30px] w-[30px] items-center justify-center rounded-lg text-faint hover:bg-subtle hover:text-brand disabled:opacity-50"
                        aria-label={`Open ${d.file_name} in a new tab`}
                        title="Open in new tab"
                      >
                        <ArrowSquareOut size={16} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(d)}
                        className="flex h-[30px] w-[30px] items-center justify-center rounded-lg text-faint hover:bg-danger-soft hover:text-destructive"
                        aria-label={`Delete ${d.file_name}`}
                        title="Delete"
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        title="Delete document?"
        description={
          deleteTarget ? (
            <>
              <b className="font-semibold text-body">{deleteTarget.file_name}</b> and all its
              extracted chunks, tables and images will be permanently removed. This can&apos;t be
              undone.
            </>
          ) : null
        }
        loading={del.isPending}
        onConfirm={() => {
          if (deleteTarget) {
            del.mutate(
              { id: deleteTarget.id, companyId },
              { onSuccess: () => setDeleteTarget(null) },
            );
          }
        }}
      />
    </div>
  );
}
