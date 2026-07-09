import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { CaretRight, Check, Image, Lock, Minus, Plus, TextT, Trash } from "@phosphor-icons/react";

import {
  createMaterialErrorText as errorText,
} from "@/lib/api/materials";
import { useCreateTemplate, type TemplateImageSlot } from "@/lib/api/templates";
import { slugifyId, toImageSlots } from "@/lib/template-builder";

// Bounds mirror the backend serializer (spec §5.1).
const BOUNDS = {
  headline: { min: 1, max: 60 },
  subheadline: { min: 1, max: 60 },
  cta: { min: 1, max: 60 },
  bodyWords: { min: 1, max: 300 },
  bodyRows: { min: 1, max: 10 },
  slots: { max: 8 },
};

function Stepper({
  value,
  min,
  max,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <span className="flex items-center gap-1 rounded-lg border border-field px-1 py-[2px]">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        className="p-1 text-mute hover:text-body"
        aria-label="decrease"
      >
        <Minus size={11} />
      </button>
      <span className="min-w-[60px] text-center text-[12px] text-body">≤ {value} words</span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        className="p-1 text-mute hover:text-body"
        aria-label="increase"
      >
        <Plus size={11} />
      </button>
    </span>
  );
}

function BuilderCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-5">
      <h3 className="mb-4 text-[13px] font-semibold text-ink">{title}</h3>
      {children}
    </div>
  );
}

type SlotRow = { label: string; spec: string; source: TemplateImageSlot["source"] };

export function TemplateNewPage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [headlineMax, setHeadlineMax] = useState(10);
  const [subheadlineMax, setSubheadlineMax] = useState(22);
  const [ctaMax, setCtaMax] = useState(15);
  const [bodyRows, setBodyRows] = useState(2);
  const [bodyMax, setBodyMax] = useState(80);
  const [slots, setSlots] = useState<SlotRow[]>([
    { label: "Hero image", spec: "1200×630", source: "generated_placeholder" },
    { label: "Sender logo", spec: "SVG/PNG", source: "sender" },
  ]);
  const [primary, setPrimary] = useState("#5b5bd6");
  const [accent, setAccent] = useState("#0f172a");
  const [error, setError] = useState<string | null>(null);

  const create = useCreateTemplate();
  const navigate = useNavigate();
  const slug = slugifyId(name);

  const save = () => {
    setError(null);
    create.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        constraints: {
          headline_max_words: headlineMax,
          subheadline_max_words: subheadlineMax,
          body_section_count: bodyRows,
          body_section_max_words: bodyMax,
          cta_max_words: ctaMax,
        },
        image_slots: toImageSlots(slots.filter((s) => s.label.trim())),
        theme: { primary_color: primary, accent_color: accent },
      },
      {
        onSuccess: () => navigate({ to: "/templates" }),
        onError: (err) => setError(errorText(err)),
      },
    );
  };

  const setSlot = (i: number, patch: Partial<SlotRow>) =>
    setSlots(slots.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  const textRow = (
    icon: React.ReactNode,
    label: string,
    stepper: React.ReactNode,
    onRemove?: () => void,
  ) => (
    <div className="flex items-center gap-3 border-b border-hairline py-2 last:border-0">
      <span className="flex size-[26px] items-center justify-center rounded-lg bg-brand-soft text-brand">
        {icon}
      </span>
      <span className="flex-1 text-[13px] font-semibold text-body">{label}</span>
      {stepper}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-mute hover:text-destructive"
          aria-label={`remove ${label}`}
        >
          <Trash size={14} />
        </button>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/templates" className="hover:text-brand">
          Templates
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">New template</span>
      </div>
      <h1 className="text-[24px] font-bold tracking-[-0.02em] text-ink">Create Template</h1>
      <p className="mb-6 mt-1 text-[13px] text-subtext">
        Define the fields, limits and image slots. Generated content is validated against
        these constraints.
      </p>

      <div className="grid grid-cols-[1.5fr_1fr] items-start gap-5">
        <div className="flex flex-col gap-4">
          <BuilderCard title="Basics">
            <div className="flex flex-col gap-3">
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-body">
                  Template name
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Product Spotlight"
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-body">
                  Template ID <Lock size={11} className="text-mute" />
                </label>
                <div className="rounded-[10px] bg-[#f4f4f6] px-3 py-[8px] font-mono text-[12px] text-subtext">
                  {slug || "—"}
                </div>
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-body">
                  Description
                </label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
                />
              </div>
            </div>
          </BuilderCard>

          <BuilderCard title="Text fields">
            {textRow(
              <TextT size={13} />,
              "Headline",
              <Stepper
                value={headlineMax}
                min={BOUNDS.headline.min}
                max={BOUNDS.headline.max}
                onChange={setHeadlineMax}
              />,
            )}
            {textRow(
              <TextT size={13} />,
              "Subheadline",
              <Stepper
                value={subheadlineMax}
                min={BOUNDS.subheadline.min}
                max={BOUNDS.subheadline.max}
                onChange={setSubheadlineMax}
              />,
            )}
            {Array.from({ length: bodyRows }, (_, i) =>
              textRow(
                <TextT size={13} />,
                `Body section ${i + 1}`,
                // All body rows share ONE limit (fixed contract, spec §7.3).
                <Stepper
                  value={bodyMax}
                  min={BOUNDS.bodyWords.min}
                  max={BOUNDS.bodyWords.max}
                  onChange={setBodyMax}
                />,
                bodyRows > BOUNDS.bodyRows.min
                  ? () => setBodyRows(bodyRows - 1)
                  : undefined,
              ),
            )}
            {textRow(
              <TextT size={13} />,
              "CTA",
              <Stepper
                value={ctaMax}
                min={BOUNDS.cta.min}
                max={BOUNDS.cta.max}
                onChange={setCtaMax}
              />,
            )}
            <button
              type="button"
              disabled={bodyRows >= BOUNDS.bodyRows.max}
              onClick={() => setBodyRows(bodyRows + 1)}
              className="mt-3 w-full rounded-[10px] border border-dashed border-field py-[8px] text-[12.5px] font-semibold text-brand hover:bg-subtle disabled:opacity-40"
            >
              + Add text field (body section)
            </button>
          </BuilderCard>

          <BuilderCard title="Image slots">
            {slots.map((slot, i) => (
              <div
                key={i}
                className="flex items-center gap-3 border-b border-hairline py-2 last:border-0"
              >
                <span className="flex size-[26px] items-center justify-center rounded-lg bg-review-soft text-review">
                  <Image size={13} />
                </span>
                <input
                  value={slot.label}
                  onChange={(e) => setSlot(i, { label: e.target.value })}
                  placeholder="Slot name"
                  className="flex-1 rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12.5px] font-semibold text-body outline-none focus:border-brand"
                />
                <input
                  value={slot.spec}
                  onChange={(e) => setSlot(i, { spec: e.target.value })}
                  placeholder="Spec (e.g. 1200×630)"
                  className="w-[120px] rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12px] text-body outline-none focus:border-brand"
                />
                <select
                  value={slot.source}
                  onChange={(e) =>
                    setSlot(i, { source: e.target.value as SlotRow["source"] })
                  }
                  className="rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12px] text-body outline-none"
                >
                  <option value="generated_placeholder">Placeholder</option>
                  <option value="sender">Sender</option>
                  <option value="receiver">Receiver</option>
                </select>
                <button
                  type="button"
                  onClick={() => setSlots(slots.filter((_, j) => j !== i))}
                  className="text-mute hover:text-destructive"
                  aria-label={`remove slot ${slot.label}`}
                >
                  <Trash size={14} />
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={slots.length >= BOUNDS.slots.max}
              onClick={() =>
                setSlots([...slots, { label: "", spec: "", source: "generated_placeholder" }])
              }
              className="mt-3 w-full rounded-[10px] border border-dashed border-field py-[8px] text-[12.5px] font-semibold text-brand hover:bg-subtle disabled:opacity-40"
            >
              + Add image slot
            </button>
          </BuilderCard>

          <BuilderCard title="Theme colors">
            <div className="flex gap-6">
              {(
                [
                  ["Primary", primary, setPrimary],
                  ["Accent", accent, setAccent],
                ] as const
              ).map(([label, value, set]) => (
                <div key={label} className="flex items-center gap-2">
                  <span
                    className="size-[28px] rounded-lg border border-hairline"
                    style={{ background: value }}
                  />
                  <div>
                    <div className="text-[11px] font-semibold text-body">{label}</div>
                    <input
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      className="w-[90px] rounded border border-field bg-subtle px-1 py-[2px] font-mono text-[11.5px] text-body outline-none"
                    />
                  </div>
                </div>
              ))}
            </div>
          </BuilderCard>
        </div>

        <div className="sticky top-[26px] flex flex-col gap-4">
          <div className="rounded-2xl border border-hairline bg-surface p-5">
            <h3 className="mb-3 text-[13px] font-semibold text-ink">Live layout preview</h3>
            {slots.some((s) => s.source === "generated_placeholder") && (
              <div
                className="mb-3 flex h-[90px] items-center justify-center rounded-lg text-[11px] text-mute"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, #ececf0 0 10px, #f6f6f8 10px 20px)",
                }}
              >
                Hero image
              </div>
            )}
            <div className="mb-2 h-[14px] w-3/4 rounded bg-[#e7e7ec]" />
            <div className="mb-3 h-[9px] w-full rounded bg-[#f0f0f2]" />
            {Array.from({ length: bodyRows }, (_, i) => (
              <div key={i} className="mb-2 h-[9px] w-full rounded bg-[#f0f0f2]" />
            ))}
            <div
              className="mt-3 h-[30px] rounded-lg"
              style={{ background: `${primary}22` }}
            />
            <div className="mt-4 flex gap-2 text-[11px] text-subtext">
              <span className="rounded-full border border-hairline px-2 py-[2px]">
                {3 + bodyRows} text fields
              </span>
              <span className="rounded-full border border-hairline px-2 py-[2px]">
                {slots.length} image slots
              </span>
            </div>
          </div>
          <p className="rounded-xl bg-brand-soft px-4 py-3 text-[12px] text-body">
            This template compiles to the same layout-JSON schema every generation is
            validated against.
          </p>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-[12.5px] text-destructive">
          {error}
        </p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <Link
          to="/templates"
          className="rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold text-subtext hover:text-body"
        >
          Cancel
        </Link>
        <button
          type="button"
          disabled={!name.trim() || create.isPending}
          onClick={save}
          className="flex items-center gap-2 rounded-[10px] bg-brand px-[18px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
        >
          <Check size={15} weight="bold" />
          Save template
        </button>
      </div>
    </div>
  );
}
