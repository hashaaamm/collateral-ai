import { Link } from "@tanstack/react-router";
import { Newspaper, Plus } from "@phosphor-icons/react";

import { templateConstraints, templateImageSlots, useTemplates } from "@/lib/api/templates";

export function TemplatesPage() {
  const { data: templates, isLoading } = useTemplates();
  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-center">
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">Templates</h1>
          <p className="mt-1 text-[13px] text-subtext">
            Publishing layouts and the constraints generations are validated against.
          </p>
        </div>
        <Link
          to="/templates/new"
          className="ml-auto flex items-center gap-[7px] rounded-[10px] bg-brand px-[14px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus size={15} weight="bold" />
          New Template
        </Link>
      </div>

      {isLoading && <p className="text-[13px] text-mute">Loading…</p>}

      <div className="grid grid-cols-[1.4fr_1fr] items-start gap-5">
        <div className="flex flex-col gap-4">
          {(templates ?? []).map((t) => {
            const constraints = templateConstraints(t);
            const slots = templateImageSlots(t);
            const theme = t.theme as { primary_color: string; accent_color: string };
            return (
              <div key={t.id} className="rounded-2xl border border-hairline bg-surface p-5">
                <div className="mb-4 flex items-center gap-3">
                  <span className="flex size-[34px] items-center justify-center rounded-lg bg-brand-soft text-brand">
                    <Newspaper size={17} />
                  </span>
                  <div>
                    <div className="text-[14px] font-semibold text-ink">{t.name}</div>
                    <div className="font-mono text-[11px] text-mute">{t.slug}</div>
                  </div>
                  {t.is_active && (
                    <span className="ml-auto rounded-full bg-success-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-success">
                      Active
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4 text-[12.5px] text-subtext">
                  <div>
                    <div className="mb-1 font-semibold text-body">Field constraints</div>
                    <ul className="leading-relaxed">
                      <li>Headline ≤{constraints.headline_max_words}</li>
                      <li>Subheadline ≤{constraints.subheadline_max_words}</li>
                      <li>
                        Body {constraints.body_section_count}×≤
                        {constraints.body_section_max_words}
                      </li>
                      <li>CTA ≤{constraints.cta_max_words}</li>
                    </ul>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold text-body">Image slots</div>
                    <ul className="leading-relaxed">
                      {slots.length === 0 && <li>None</li>}
                      {slots.map((s) => (
                        <li key={s.slot_id}>
                          {s.label} {s.spec && `(${s.spec})`}
                        </li>
                      ))}
                    </ul>
                    <div className="mb-1 mt-3 font-semibold text-body">Theme</div>
                    <div className="flex items-center gap-2">
                      {[theme.primary_color, theme.accent_color].map((hex, i) => (
                        <span key={i} className="flex items-center gap-1">
                          <span
                            className="size-[16px] rounded border border-hairline"
                            style={{ background: hex }}
                          />
                          <span className="font-mono text-[11px]">{hex}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col gap-4">
          {["Brochure (Tri-fold)", "Email Campaign"].map((name) => (
            <div
              key={name}
              className="rounded-2xl border border-dashed border-hairline bg-surface p-5 opacity-70"
            >
              <div className="text-[13.5px] font-semibold text-ink">{name}</div>
              <p className="mt-1 text-[12px] text-mute">
                Coming soon — same JSON contract.
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
