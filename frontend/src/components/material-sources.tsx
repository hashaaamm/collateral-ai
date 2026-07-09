import type { ReactNode } from "react";
import { ArrowDownLeft, ArrowSquareOut, ArrowUpRight, FilePdf } from "@phosphor-icons/react";

import { fetchDocumentViewUrl } from "@/lib/api/documents";
import type { MaterialDetail } from "@/lib/api/materials";

type Source = MaterialDetail["sources"][number];

async function openSource(source: Source) {
  try {
    const url = await fetchDocumentViewUrl(source.document.company, source.document.id);
    const suffix = source.page_number != null ? `#page=${source.page_number}` : "";
    window.open(url + suffix, "_blank", "noopener");
  } catch {
    // Viewing is unavailable when GCS isn't configured (503) — nothing to open.
  }
}

function SourceCard({ source }: { source: Source }) {
  return (
    <div className="rounded-[11px] border border-hairline p-3">
      <div className="flex items-center gap-2">
        <FilePdf size={16} className="shrink-0 text-danger" />
        <span className="min-w-0 truncate text-[12.5px] font-semibold text-ink">
          {source.document.file_name}
        </span>
        {source.page_number != null && (
          <span className="font-mono text-[11px] text-mute">p.{source.page_number}</span>
        )}
        <button
          type="button"
          onClick={() => void openSource(source)}
          className="ml-auto text-mute hover:text-brand"
          aria-label={`Open ${source.document.file_name}`}
        >
          <ArrowSquareOut size={15} />
        </button>
      </div>
      {source.snippet && (
        <p className="mt-2 text-[12px] italic leading-relaxed text-subtext">
          "{source.snippet}"
        </p>
      )}
      {source.used_fact && (
        <p className="mt-1 text-[11.5px] text-mute">Used: {source.used_fact}</p>
      )}
    </div>
  );
}

function SourceColumn({
  title,
  badge,
  sources,
}: {
  title: string;
  badge: ReactNode;
  sources: Source[];
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-[12.5px] font-semibold text-ink">
        {badge}
        {title}
      </div>
      <div className="flex flex-col gap-2">
        {sources.length === 0 && <p className="text-[12px] text-mute">No sources cited.</p>}
        {sources.map((s) => (
          <SourceCard key={s.id} source={s} />
        ))}
      </div>
    </div>
  );
}

export function MaterialSources({ material }: { material: MaterialDetail }) {
  const sender = material.sources.filter((s) => s.source_role === "sender");
  const receiver = material.sources.filter((s) => s.source_role === "receiver");
  return (
    <div>
      <p className="mb-3 text-[12.5px] text-subtext">
        Every claim is grounded in these document excerpts.
      </p>
      <div className="grid grid-cols-2 gap-5">
        <SourceColumn
          title={`Sender — ${material.sender_company.name}`}
          badge={<ArrowUpRight size={14} className="text-brand" weight="bold" />}
          sources={sender}
        />
        <SourceColumn
          title={`Receiver — ${material.receiver_company.name}`}
          badge={<ArrowDownLeft size={14} className="text-review" weight="bold" />}
          sources={receiver}
        />
      </div>
    </div>
  );
}
