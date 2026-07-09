import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
  ArrowsClockwise,
  CaretRight,
  Check,
  CheckCircle,
  CircleNotch,
  Copy,
  PencilSimple,
  Prohibit,
  Trash,
  XCircle,
} from "@phosphor-icons/react";

import { MaterialJson } from "@/components/material-json";
import { MaterialSources } from "@/components/material-sources";
import { NewsletterPreview } from "@/components/newsletter-preview";
import { StatusPill, materialPillStatus } from "@/components/status-pill";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  isGenerating,
  outputJson,
  useDeleteMaterial,
  useMaterial,
  useRegenerateMaterial,
  useUpdateMaterial,
  validationResult,
  type MaterialDetail,
} from "@/lib/api/materials";
import { templateConstraints } from "@/lib/api/templates";

const TABS = ["Preview", "Layout JSON", "Sources"] as const;
type Tab = (typeof TABS)[number];

const STALE_MS = 15 * 60 * 1000; // spec §5.2: stuck-row escape hatch

const words = (s: string) => (s ? s.trim().split(/\s+/).length : 0);

const QUALITY_CHECKS: [string, string][] = [
  ["structure", "JSON schema valid"],
  ["word_limit", "Word limits passed"],
  ["image_slot", "Image slots present"],
  ["source", "Sources attached"],
];

function RailCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-4">
      <h3 className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-faint">
        {title}
      </h3>
      {children}
    </div>
  );
}

function QualityChecks({ material }: { material: MaterialDetail }) {
  const result = validationResult(material);
  if (!result) return <p className="text-[12px] text-mute">No validation run yet.</p>;
  const failing = new Set(result.errors.map((e) => e.category));
  return (
    <div className="flex flex-col gap-2">
      {QUALITY_CHECKS.map(([category, label]) => {
        const ok = !failing.has(category);
        return (
          <div key={category} className="flex items-center gap-2 text-[12.5px] text-body">
            {ok ? (
              <CheckCircle size={17} weight="fill" className="text-success" />
            ) : (
              <XCircle size={17} weight="fill" className="text-destructive" />
            )}
            {label}
          </div>
        );
      })}
    </div>
  );
}

function ConstraintMeters({ material }: { material: MaterialDetail }) {
  const output = outputJson(material);
  if (!output) return null;
  const constraints = templateConstraints(material.template);
  const meters = [
    { label: "Headline", used: words(output.article.headline), limit: constraints.headline_max_words },
    { label: "Subheadline", used: words(output.article.subheadline), limit: constraints.subheadline_max_words },
    ...output.article.body_sections.map((section) => ({
      label: `Body · ${section.title}`,
      used: words(section.text),
      limit: constraints.body_section_max_words,
    })),
    { label: "CTA", used: words(output.article.cta), limit: constraints.cta_max_words },
  ];
  return (
    <div className="flex flex-col gap-3">
      {meters.map((meter) => {
        const ratio = meter.limit ? meter.used / meter.limit : 0;
        const amber = ratio >= 2 / 3; // reproduces the design's examples (spec §7.3)
        return (
          <div key={meter.label}>
            <div className="mb-1 flex items-center justify-between text-[11.5px]">
              <span className={amber ? "text-warning" : "text-body"}>{meter.label}</span>
              <span className="font-mono text-mute">
                {meter.used}/{meter.limit}
              </span>
            </div>
            <div className="h-[5px] rounded-full bg-[#f0f0f2]">
              <div
                className={`h-full rounded-full ${amber ? "bg-[#e0a83b]" : "bg-success"}`}
                style={{ width: `${Math.min(100, ratio * 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EditPromptDialog({ material }: { material: MaterialDetail }) {
  const [prompt, setPrompt] = useState(material.prompt);
  const update = useUpdateMaterial(material.id);
  return (
    <AlertDialog>
      <AlertDialogTrigger className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle">
        <PencilSimple size={15} />
        Edit prompt
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Edit prompt</AlertDialogTitle>
          <AlertDialogDescription>
            Saving does not regenerate — use Regenerate afterwards to apply it.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={5}
          className="w-full rounded-[10px] border border-field bg-subtle p-3 text-[13px] text-body outline-none focus:border-brand"
        />
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => update.mutate({ prompt })}>Save</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function MaterialDetailPage() {
  const { materialId } = useParams({ from: "/app/materials/$materialId" });
  const { data: material, isLoading, isError } = useMaterial(Number(materialId));
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("Preview");
  const update = useUpdateMaterial(Number(materialId));
  const regenerate = useRegenerateMaterial(Number(materialId));
  const del = useDeleteMaterial();

  // spec §5.2: stuck-row escape hatch. Date.now() must run inside an effect,
  // not render, to stay pure (react-hooks/purity) — recheck every 30s so a
  // material stuck mid-generation eventually unlocks Regenerate without a reload.
  const updatedAt = material?.updated_at;
  const [stale, setStale] = useState(false);
  useEffect(() => {
    if (!updatedAt) return;
    const updatedAtMs = new Date(updatedAt).getTime();
    const check = () => setStale(Date.now() - updatedAtMs > STALE_MS);
    check();
    const id = window.setInterval(check, 30_000);
    return () => window.clearInterval(id);
  }, [updatedAt]);

  if (isLoading) {
    return <div className="mx-auto max-w-[1120px] px-10 pt-8 text-sm text-mute">Loading…</div>;
  }
  if (isError || !material) {
    return (
      <div className="mx-auto max-w-[1120px] px-10 pt-8">
        <p className="text-sm text-destructive">Material not found.</p>
        <Link to="/materials" className="mt-2 inline-block text-sm text-brand">
          Back to marketing requests
        </Link>
      </div>
    );
  }

  const output = outputJson(material);
  const generating = isGenerating(material);
  const completed = material.generation_status === "completed";
  const copyJson = () =>
    void navigator.clipboard.writeText(JSON.stringify(material.output_json, null, 2));
  const setReview = (value: "approved" | "rejected") =>
    update.mutate({
      review_status: material.review_status === value ? "pending" : value,
    });

  return (
    <div className="mx-auto max-w-[1120px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/materials" className="hover:text-brand">
          Marketing Requests
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">{material.title}</span>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">{material.title}</h1>
        <StatusPill
          status={materialPillStatus({
            // generation_status/review_status are optional in the generated type
            // (DRF field defaults make them non-required on the response contract,
            // see materials.ts:isGenerating) but always present in practice — the
            // model defaults to "queued"/"pending" (models.py).
            generation_status: material.generation_status ?? "queued",
            review_status: material.review_status ?? "pending",
          })}
        />
        <div className="ml-auto flex items-center gap-[9px]">
          <button
            type="button"
            disabled={(generating && !stale) || regenerate.isPending}
            onClick={() => regenerate.mutate()}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle disabled:opacity-50"
          >
            <ArrowsClockwise size={15} />
            Regenerate
          </button>
          <EditPromptDialog material={material} />
          {completed && (
            <>
              <button
                type="button"
                onClick={() => setReview("approved")}
                className={`flex items-center gap-[7px] rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold ${
                  material.review_status === "approved"
                    ? "bg-success text-white"
                    : "bg-[#16a34a] text-white hover:bg-[#128a3f]"
                }`}
              >
                <Check size={15} weight="bold" />
                {material.review_status === "approved" ? "Approved" : "Mark approved"}
              </button>
              <button
                type="button"
                onClick={() => setReview("rejected")}
                className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle"
              >
                <Prohibit size={15} />
                {material.review_status === "rejected" ? "Rejected" : "Reject"}
              </button>
            </>
          )}
        </div>
      </div>
      <div className="-mt-4 mb-6 text-[12.5px] text-subtext">
        <span className="font-semibold text-body">{material.sender_company.name}</span>
        {" → "}
        <span className="font-semibold text-body">{material.receiver_company.name}</span>
        {" · "}
        <span className="font-mono">{material.template_slug}</span>
        {material.completed_at && ` · Generated ${new Date(material.completed_at).toLocaleString()}`}
      </div>

      {material.generation_status === "failed" && (
        <div className="mb-5 rounded-xl border border-danger/30 bg-danger-soft p-4 text-[13px] text-destructive">
          <strong>Generation failed:</strong> {material.error_message || "Unknown error."}
          {/* JSON tab stays accessible below when output_json exists (spec §7.3). */}
        </div>
      )}

      {generating ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-hairline bg-surface py-20">
          <CircleNotch size={28} className="animate-spin text-brand" />
          <p className="text-[13.5px] text-body">Generating material…</p>
          <p className="text-[12px] text-mute">
            This usually takes under a minute. The page updates automatically.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_320px] items-start gap-[22px]">
          <div className="rounded-2xl border border-hairline bg-surface">
            <div className="flex items-center gap-5 border-b border-hairline px-5">
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`-mb-px border-b-2 py-[12px] text-[13px] font-medium ${
                    tab === t
                      ? "border-brand text-brand"
                      : "border-transparent text-mute hover:text-body"
                  }`}
                >
                  {t}
                </button>
              ))}
              {tab === "Layout JSON" && (
                <button
                  type="button"
                  onClick={copyJson}
                  className="ml-auto flex items-center gap-1 text-[12px] text-brand"
                >
                  <Copy size={13} /> Copy
                </button>
              )}
            </div>
            <div className="p-5">
              {tab === "Preview" &&
                (output ? (
                  <NewsletterPreview material={material} output={output} />
                ) : (
                  <p className="text-[13px] text-mute">No output to preview.</p>
                ))}
              {tab === "Layout JSON" &&
                (material.output_json ? (
                  <MaterialJson value={material.output_json} />
                ) : (
                  <p className="text-[13px] text-mute">No JSON stored.</p>
                ))}
              {tab === "Sources" && <MaterialSources material={material} />}
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <RailCard title="Quality checks">
              <QualityChecks material={material} />
            </RailCard>
            {output && (
              <RailCard title="Constraint meters">
                <ConstraintMeters material={material} />
              </RailCard>
            )}
            <RailCard title="Actions">
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={copyJson}
                  disabled={!material.output_json}
                  className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle disabled:opacity-50"
                >
                  <Copy size={15} />
                  Copy JSON
                </button>
                <AlertDialog>
                  <AlertDialogTrigger className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle">
                    <Trash size={15} />
                    Delete material
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete material?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This removes the generated content, layout JSON and source
                        references. This can't be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() =>
                          del.mutate(material.id, {
                            onSuccess: () => navigate({ to: "/materials" }),
                          })
                        }
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </RailCard>
          </div>
        </div>
      )}
    </div>
  );
}
