import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowClockwise, FilePdf, Trash, UploadSimple } from "@phosphor-icons/react";

import { StatusPill } from "@/components/status-pill";
import {
  useCompleteDocument,
  useDeleteDocument,
  useDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api/documents";

function num(n: number | null | undefined) {
  return n == null ? "—" : String(n);
}

export function DocumentsTab({ companyId }: { companyId: number }) {
  const qc = useQueryClient();
  const { data: docs = [], isLoading } = useDocuments(companyId);
  const retry = useCompleteDocument();
  const del = useDeleteDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string>("");

  async function onFiles(files: FileList | null) {
    if (!files) return;
    setError("");
    for (const file of Array.from(files)) {
      if (file.type !== "application/pdf") {
        setError("Only PDF files are supported.");
        continue;
      }
      setProgress(0);
      try {
        await uploadDocument({ companyId, file, onProgress: setProgress });
      } catch (e) {
        setError(
          e instanceof Error && e.message === "upload_not_configured"
            ? "Document upload isn't configured in this environment."
            : "Upload failed. Try again.",
        );
      }
    }
    setProgress(null);
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

      {progress !== null && (
        <div className="mb-4 h-[6px] w-full overflow-hidden rounded-full bg-hairline-soft">
          <div className="h-full bg-brand transition-[width]" style={{ width: `${progress}%` }} />
        </div>
      )}
      {error && <p className="mb-3 text-[12.5px] text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-[13px] text-mute">Loading…</p>
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
                <th className="px-4 py-[10px] text-right">Status</th>
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
                    <div className="flex items-center justify-end gap-2">
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
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm(`Delete "${d.file_name}"? This can't be undone.`)) {
                            del.mutate({ id: d.id, companyId });
                          }
                        }}
                        className="flex items-center gap-1 text-[12px] text-mute hover:text-destructive"
                        aria-label={`Delete ${d.file_name}`}
                      >
                        <Trash size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
