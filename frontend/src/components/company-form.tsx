import { useRef, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Buildings, Globe, Plus, UploadSimple, X } from "@phosphor-icons/react";
import { z } from "zod";

import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { requestUploadAndPut } from "@/lib/api/companies";

const schema = z.object({
  name: z.string().min(1, "Company name is required"),
  website: z.union([z.string().url("Enter a valid URL"), z.literal("")]).optional(),
  industry: z.string().optional(),
  description: z.string().optional(),
});
type Values = z.infer<typeof schema>;

const MAX_COLORS = 5;

export type CompanyFormPayload = {
  name: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors: string[];
  logo?: string;
};

export type CompanyFormInitial = {
  name?: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors?: string[];
  logoUrl?: string | null;
};

export function CompanyForm({
  initial,
  submitLabel,
  submitting,
  error,
  cancel,
  onSubmit,
}: {
  initial?: CompanyFormInitial;
  submitLabel: string;
  submitting: boolean;
  error: boolean;
  cancel: ReactNode;
  onSubmit: (payload: CompanyFormPayload) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  const [colors, setColors] = useState<string[]>(initial?.brand_colors ?? []);
  const [logoPath, setLogoPath] = useState<string>(""); // set only when a NEW logo is uploaded
  const [logoPreview, setLogoPreview] = useState<string>(initial?.logoUrl ?? "");
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "error" | "unavailable">(
    "idle",
  );
  const [pendingColorRemove, setPendingColorRemove] = useState<number | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: initial?.name ?? "",
      website: initial?.website ?? "",
      industry: initial?.industry ?? "",
      description: initial?.description ?? "",
    },
  });

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadState("uploading");
    setLogoPreview(URL.createObjectURL(file));
    try {
      setLogoPath(await requestUploadAndPut(file));
      setUploadState("idle");
    } catch (err) {
      setLogoPath("");
      setUploadState(err instanceof Error && err.message === "upload_not_configured" ? "unavailable" : "error");
    }
  }

  const submit = handleSubmit((values) => {
    onSubmit({
      name: values.name,
      website: values.website || undefined,
      industry: values.industry || undefined,
      description: values.description || undefined,
      brand_colors: colors,
      logo: logoPath || undefined, // omitted when unchanged (keeps existing logo on edit)
    });
  });

  return (
    <form onSubmit={submit}>
      <div className="rounded-2xl border border-hairline bg-surface p-[26px]">
        <div className="mb-6 flex items-center gap-4 border-b border-hairline pb-[22px]">
          {logoPreview ? (
            <img src={logoPreview} alt="Logo preview" className="size-[56px] flex-none rounded-[13px] object-cover" />
          ) : (
            <div className="flex size-[56px] flex-none items-center justify-center rounded-[13px] bg-subtle text-faint">
              <Buildings size={24} />
            </div>
          )}
          <div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange={onPickFile} aria-label="Upload company logo" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploadState === "uploading"}
              className="flex items-center gap-[7px] rounded-[9px] border border-field bg-surface px-[13px] py-2 text-[12.5px] font-semibold text-body hover:bg-subtle disabled:opacity-60"
            >
              <UploadSimple size={14} />
              {uploadState === "uploading" ? "Uploading…" : "Upload logo"}
            </button>
            <div className="mt-[6px] text-[11.5px] text-faint" aria-live="polite">
              {uploadState === "error" && <span className="text-destructive">Upload failed. Try again.</span>}
              {uploadState === "unavailable" && "Logo upload isn't configured in this environment."}
              {uploadState !== "error" && uploadState !== "unavailable" && "SVG or PNG, at least 128×128"}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-[18px_20px]">
          <div>
            <label htmlFor="name" className="mb-2 block text-[12px] font-semibold text-body">
              Company name <span className="text-destructive">*</span>
            </label>
            <Input id="name" placeholder="e.g. Acme AI" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("name")} />
            {errors.name && <p className="mt-1 text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div>
            <label htmlFor="website" className="mb-2 block text-[12px] font-semibold text-body">Website</label>
            <div className="flex items-center gap-2 rounded-[10px] border border-field bg-subtle px-3">
              <Globe size={15} className="text-faint" />
              <Input id="website" placeholder="https://acme.ai" className="h-auto border-0 bg-transparent px-0 py-[11px] text-[13.5px] shadow-none focus-visible:ring-0" {...register("website")} />
            </div>
            {errors.website && <p className="mt-1 text-xs text-destructive">{errors.website.message}</p>}
          </div>
          <div>
            <label htmlFor="industry" className="mb-2 block text-[12px] font-semibold text-body">Industry</label>
            <Input id="industry" placeholder="e.g. AI Software" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("industry")} />
          </div>
          <div>
            <label className="mb-2 block text-[12px] font-semibold text-body">Brand colors</label>
            <div className="flex items-center gap-2">
              {colors.map((hex, i) => (
                <span key={i} className="relative">
                  <input
                    type="color"
                    value={hex}
                    onChange={(e) => setColors((c) => c.map((x, j) => (j === i ? e.target.value : x)))}
                    className="size-[34px] cursor-pointer rounded-lg border border-hairline"
                  />
                  <button type="button" onClick={() => setPendingColorRemove(i)} className="absolute -right-1 -top-1 rounded-full bg-surface text-mute" aria-label="Remove color">
                    <X size={12} />
                  </button>
                </span>
              ))}
              {colors.length < MAX_COLORS && (
                <button type="button" onClick={() => setColors((c) => [...c, "#5b5bd6"])} className="flex size-[34px] items-center justify-center rounded-lg border border-dashed border-field text-faint hover:bg-subtle" aria-label="Add color">
                  <Plus weight="bold" size={14} />
                </button>
              )}
            </div>
          </div>
          <div className="col-span-2">
            <label htmlFor="description" className="mb-2 block text-[12px] font-semibold text-body">Description</label>
            <textarea id="description" rows={2} placeholder="One line on what the company does." className="w-full resize-none rounded-[10px] border border-field bg-subtle px-3 py-[11px] text-[13.5px] leading-[1.55] text-ink outline-none" {...register("description")} />
          </div>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-destructive">Something went wrong. Please try again.</p>}

      <div className="mt-5 flex justify-end gap-[9px]">
        {cancel}
        <Button type="submit" disabled={submitting || uploadState === "uploading"} className="flex h-auto items-center gap-[7px] rounded-[10px] bg-brand px-[18px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover">
          {submitting ? "Saving…" : <>{submitLabel} <ArrowRight weight="bold" size={14} /></>}
        </Button>
      </div>

      <ConfirmDeleteDialog
        open={pendingColorRemove !== null}
        onOpenChange={(o) => {
          if (!o) setPendingColorRemove(null);
        }}
        title="Remove color?"
        description="This color will be removed from the brand palette."
        confirmLabel="Remove"
        onConfirm={() => {
          setColors((c) => c.filter((_, j) => j !== pendingColorRemove));
          setPendingColorRemove(null);
        }}
      />
    </form>
  );
}
