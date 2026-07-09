import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Check, CheckCircle, MagicWand, MagnifyingGlass } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { api } from "@/lib/api/client";
import { useCompanies, type Company } from "@/lib/api/companies";
import { createMaterialErrorText, useCreateMaterial } from "@/lib/api/materials";
import { templateConstraints, templateImageSlots, useTemplates } from "@/lib/api/templates";
import { useDebouncedValue } from "@/lib/use-debounced-value";

const STEPS = ["Companies", "Template", "Prompt", "Generate"] as const;
const TONES = ["Professional", "Friendly", "Executive", "Technical"] as const;
const CTA_STYLES = ["Soft", "Direct"] as const;

/** Processed-doc count for a selected company (drives the grounding strip). */
function useProcessedDocCount(companyId: number | undefined) {
  return useQuery({
    queryKey: ["documents", companyId],
    enabled: companyId != null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/{company_pk}/documents/", {
        params: { path: { company_pk: companyId as number } },
      });
      if (error) throw error;
      return data;
    },
    select: (docs) => docs.filter((d) => d.status === "processed").length,
  });
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-[12px] py-[5px] text-[12px] font-semibold ${
        active
          ? "border-[#dcdcfb] bg-brand-soft text-brand"
          : "border-[#e6e6ea] bg-surface text-subtext hover:text-body"
      }`}
    >
      {label}
    </button>
  );
}

function CompanyPicker({
  label,
  selected,
  exclude,
  onSelect,
}: {
  label: string;
  selected: Company | null;
  exclude: number | undefined;
  onSelect: (company: Company) => void;
}) {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const { data: companies, isLoading } = useCompanies(debounced);
  const results = (companies ?? []).filter((c) => c.id !== exclude);
  return (
    <div>
      <div className="mb-2 text-[12px] font-semibold text-body">{label}</div>
      <div className="relative mb-2">
        <MagnifyingGlass
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-mute"
        />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies…"
          className="w-full rounded-[10px] border border-field bg-subtle py-[8px] pl-8 pr-3 text-[13px] text-body outline-none focus:border-brand"
        />
      </div>
      <div className="max-h-[220px] overflow-y-auto rounded-xl border border-hairline">
        {isLoading && <p className="p-3 text-[12.5px] text-mute">Searching…</p>}
        {!isLoading && results.length === 0 && (
          <p className="p-3 text-[12.5px] text-mute">No companies found.</p>
        )}
        {results.map((company) => {
          const isSelected = selected?.id === company.id;
          return (
            <button
              key={company.id}
              type="button"
              onClick={() => onSelect(company)}
              className={`flex w-full items-center gap-3 border-b border-hairline p-3 text-left last:border-0 ${
                isSelected
                  ? "border-l-[3px] border-l-brand bg-[#f4f4fd]"
                  : "hover:bg-[#fafafb]"
              }`}
            >
              <CompanyLogo name={company.name} logoUrl={company.logo_url} size={30} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-ink">
                  {company.name}
                </span>
                <span className="block truncate text-[11.5px] text-mute">
                  {company.industry || "—"}
                </span>
              </span>
              {isSelected && <CheckCircle size={18} weight="fill" className="text-brand" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function CreatePage() {
  const [step, setStep] = useState(0);
  const [sender, setSender] = useState<Company | null>(null);
  const [receiver, setReceiver] = useState<Company | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [tone, setTone] = useState<string>("Professional");
  const [ctaStyle, setCtaStyle] = useState<string>("Soft");
  const [ctaLink, setCtaLink] = useState("");
  const [language, setLanguage] = useState("English");
  const [error, setError] = useState<string | null>(null);

  const { data: templates } = useTemplates();
  const activeTemplates = (templates ?? []).filter((t) => t.is_active);
  // Pre-select the default (first active = the seed, oldest-first ordering, spec §7.3)
  // as a derived value — computed at render time instead of via a setState-in-effect,
  // so it's live the moment templates load and the user can still override it by clicking.
  const selectedTemplateId = templateId ?? activeTemplates[0]?.id ?? null;
  const template = activeTemplates.find((t) => t.id === selectedTemplateId) ?? null;

  const senderDocs = useProcessedDocCount(sender?.id);
  const receiverDocs = useProcessedDocCount(receiver?.id);
  const create = useCreateMaterial();
  const navigate = useNavigate();

  const stepValid = [
    Boolean(
      sender &&
        receiver &&
        sender.id !== receiver.id &&
        (senderDocs.data ?? 0) > 0 &&
        (receiverDocs.data ?? 0) > 0,
    ),
    selectedTemplateId != null,
    title.trim().length > 0 && prompt.trim().length > 0,
    true,
  ][step];

  const generate = () => {
    if (!sender || !receiver || selectedTemplateId == null) return;
    setError(null);
    create.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        sender_company: sender.id,
        receiver_company: receiver.id,
        template: selectedTemplateId,
        prompt: prompt.trim(),
        tone: tone.toLowerCase(),
        cta_style: ctaStyle.toLowerCase(),
        cta_link: ctaLink.trim() || undefined,
        language: language.toLowerCase(),
      },
      {
        onSuccess: (material) =>
          navigate({
            to: "/materials/$materialId",
            params: { materialId: String(material.id) },
          }),
        onError: (err) => setError(createMaterialErrorText(err)),
      },
    );
  };

  const summaryRows: [string, string][] = [
    ["Sender", sender?.name ?? "—"],
    ["Receiver", receiver?.name ?? "—"],
    ["Template", template?.name ?? "—"],
    ["Tone / CTA", `${tone} / ${ctaStyle}`],
    ["CTA link", ctaLink.trim() || "—"],
    [
      "Grounding",
      `${(senderDocs.data ?? 0) + (receiverDocs.data ?? 0)} processed documents across both companies`,
    ],
  ];

  return (
    <div className="mx-auto max-w-[820px] px-10 pb-[60px] pt-8">
      <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">Create Material</h1>
      <p className="mb-6 mt-1 text-[13px] text-subtext">
        Configure sender, receiver, template and campaign goal — then generate.
      </p>

      <div className="mb-7 flex items-center">
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center">
              <div
                className={`flex size-[30px] items-center justify-center rounded-full text-[13px] font-semibold ${
                  i <= step ? "bg-brand text-white" : "bg-[#ececf0] text-faint"
                }`}
              >
                {i < step ? <Check size={14} weight="bold" /> : i + 1}
              </div>
              <span className="mt-1 text-[11px] text-subtext">{label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`mx-2 mb-4 h-[2px] flex-1 ${i < step ? "bg-brand" : "bg-[#ececf0]"}`}
              />
            )}
          </div>
        ))}
      </div>

      <div className="min-h-[300px] rounded-2xl border border-hairline bg-surface p-6">
        {step === 0 && (
          <>
            <div className="grid grid-cols-2 gap-5">
              <CompanyPicker
                label="Sender"
                selected={sender}
                exclude={receiver?.id}
                onSelect={setSender}
              />
              <CompanyPicker
                label="Receiver"
                selected={receiver}
                exclude={sender?.id}
                onSelect={setReceiver}
              />
            </div>
            {sender && receiver && (
              <div className="mt-4 rounded-xl bg-brand-soft px-4 py-3 text-[12.5px] text-body">
                <strong>{sender.name}</strong> is pitching to <strong>{receiver.name}</strong>
                {" — grounding will draw from "}
                {(senderDocs.data ?? 0) + (receiverDocs.data ?? 0)} processed documents across
                both companies.
                {(senderDocs.data === 0 || receiverDocs.data === 0) && (
                  <span className="mt-1 block font-semibold text-destructive">
                    {senderDocs.data === 0 ? sender.name : receiver.name} has no processed
                    documents — upload and process documents first.
                  </span>
                )}
              </div>
            )}
          </>
        )}

        {step === 1 && (
          <div className="grid grid-cols-2 gap-4">
            {activeTemplates.map((t) => {
              const constraints = templateConstraints(t);
              const isSelected = t.id === selectedTemplateId;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplateId(t.id)}
                  className={`relative rounded-xl border p-4 text-left ${
                    isSelected ? "border-[1.5px] border-brand" : "border-hairline hover:bg-subtle"
                  }`}
                >
                  {isSelected && (
                    <CheckCircle
                      size={18}
                      weight="fill"
                      className="absolute right-3 top-3 text-brand"
                    />
                  )}
                  <div className="text-[13.5px] font-semibold text-ink">{t.name}</div>
                  <div className="mb-2 font-mono text-[11px] text-mute">{t.slug}</div>
                  <ul className="text-[12px] leading-relaxed text-subtext">
                    <li>Headline ≤{constraints.headline_max_words} words</li>
                    <li>Subheadline ≤{constraints.subheadline_max_words} words</li>
                    <li>
                      Body {constraints.body_section_count} sections ≤
                      {constraints.body_section_max_words} words each
                    </li>
                    <li>CTA ≤{constraints.cta_max_words} words</li>
                    <li>{templateImageSlots(t).map((s) => s.label).join(" + ") || "No images"}</li>
                  </ul>
                </button>
              );
            })}
            <div className="rounded-xl border border-dashed border-hairline p-4 opacity-65">
              <div className="text-[13.5px] font-semibold text-ink">Brochure (Tri-fold)</div>
              <div className="text-[12px] text-mute">Coming soon</div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-4">
            {/* Title + Description are deliberate additions to the design's step (spec §7.3) */}
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. AI for Smarter Logistics"
                className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">
                Description <span className="font-normal text-mute">(optional)</span>
              </label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">
                Campaign goal
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                placeholder="e.g. Generate a short B2B article about how we can help the receiver improve warehouse efficiency."
                className="w-full rounded-[10px] border border-field bg-subtle p-3 text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">
                CTA link <span className="font-normal text-mute">(optional)</span>
              </label>
              <input
                type="url"
                value={ctaLink}
                onChange={(e) => setCtaLink(e.target.value)}
                placeholder="https://example.com/book-a-demo"
                className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">Tone</div>
                <div className="flex flex-wrap gap-2">
                  {TONES.map((t) => (
                    <Chip key={t} label={t} active={tone === t} onClick={() => setTone(t)} />
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">CTA style</div>
                <div className="flex gap-2">
                  {CTA_STYLES.map((c) => (
                    <Chip
                      key={c}
                      label={c}
                      active={ctaStyle === c}
                      onClick={() => setCtaStyle(c)}
                    />
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">Language</div>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none"
                >
                  <option>English</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="mb-5 flex flex-col gap-2">
              {summaryRows.map(([label, value]) => (
                <div key={label} className="flex justify-between border-b border-hairline pb-2">
                  <span className="text-[12.5px] text-mute">{label}</span>
                  <span className="text-[13px] font-medium text-body">{value}</span>
                </div>
              ))}
            </div>
            {error && (
              <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-[12.5px] text-destructive">
                {error}
              </p>
            )}
            <button
              type="button"
              disabled={create.isPending}
              onClick={generate}
              className="flex w-full items-center justify-center gap-2 rounded-[10px] bg-brand py-[12px] text-[14px] font-semibold text-white hover:bg-brand-hover disabled:opacity-60"
            >
              <MagicWand size={17} weight="fill" />
              {create.isPending ? "Starting generation…" : "Generate Marketing Material"}
            </button>
          </div>
        )}
      </div>

      <div className="mt-5 flex justify-between">
        <button
          type="button"
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold text-subtext hover:text-body disabled:opacity-0"
        >
          Back
        </button>
        {step < 3 && (
          <button
            type="button"
            disabled={!stepValid}
            onClick={() => setStep(step + 1)}
            className="rounded-[10px] bg-ink px-[18px] py-[9px] text-[13px] font-semibold text-white disabled:opacity-40"
          >
            Continue
          </button>
        )}
      </div>
    </div>
  );
}
