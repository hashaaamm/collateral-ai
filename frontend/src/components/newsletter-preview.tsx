import { CalendarCheck } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import type { MaterialDetail, OutputJson } from "@/lib/api/materials";
import { templateImageSlots } from "@/lib/api/templates";

/** Generic slot rendering (spec §7.3) so builder-created templates work:
 *  slots render in template order — the first generated_placeholder slot is the
 *  hero block; sender/receiver slots are floating CompanyLogo chips; any further
 *  generated_placeholder slots render as smaller striped blocks. */
export function NewsletterPreview({
  material,
  output,
}: {
  material: MaterialDetail;
  output: OutputJson;
}) {
  const theme = output.theme;
  const templateSlots = templateImageSlots(material.template);
  const slotMeta = new Map(templateSlots.map((s) => [s.slot_id, s]));
  const ordered = templateSlots
    .map((t) => output.image_slots.find((s) => s.slot_id === t.slot_id))
    .filter((s): s is OutputJson["image_slots"][number] => Boolean(s));

  const heroIndex = ordered.findIndex((s) => s.source === "generated_placeholder");
  const hero = heroIndex >= 0 ? ordered[heroIndex] : null;
  const logoSlots = ordered.filter((s) => s.source === "sender" || s.source === "receiver");
  const extras = ordered.filter(
    (s, i) => s.source === "generated_placeholder" && i !== heroIndex,
  );

  const stripe = {
    backgroundImage:
      "repeating-linear-gradient(45deg, #ececf0 0 10px, #f6f6f8 10px 20px)",
  };
  const slotCaption = (slotId: string) => {
    const meta = slotMeta.get(slotId);
    return meta ? `${meta.label} · ${meta.spec}` : slotId;
  };

  return (
    <div className="mx-auto max-w-[460px] overflow-hidden rounded-2xl border border-hairline bg-surface shadow-[0_8px_30px_-12px_rgba(20,20,40,0.25)]">
      {hero && (
        <div className="relative flex h-[170px] items-end justify-center" style={stripe}>
          <span className="mb-3 rounded-md bg-surface/90 px-2 py-1 text-[11px] text-mute">
            {slotCaption(hero.slot_id)}
          </span>
          {logoSlots.length > 0 && (
            <div className="absolute left-4 top-4 flex gap-2">
              {logoSlots.map((slot) => {
                const company =
                  slot.source === "sender" ? material.sender_company : material.receiver_company;
                return (
                  <span
                    key={slot.slot_id}
                    className="rounded-xl bg-surface p-1 shadow-sm"
                    title={slotCaption(slot.slot_id)}
                  >
                    <CompanyLogo name={company.name} logoUrl={company.logo_url} size={32} />
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
      <div className="p-6">
        <div
          className="text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: theme.primary_color }}
        >
          {material.sender_company.name} × {material.receiver_company.name}
        </div>
        <h2
          className="mt-2 text-[22px] font-bold leading-tight"
          style={{ color: theme.accent_color }}
        >
          {output.article.headline}
        </h2>
        <p className="mt-2 text-[13.5px] text-subtext">{output.article.subheadline}</p>
        {output.article.body_sections.map((section, i) => (
          <div key={i} className="mt-4">
            <h3 className="text-[13px] font-semibold text-ink">{section.title}</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-body">{section.text}</p>
          </div>
        ))}
        {extras.map((slot) => (
          <div
            key={slot.slot_id}
            className="mt-4 flex h-[90px] items-center justify-center rounded-lg"
            style={stripe}
          >
            <span className="rounded-md bg-surface/90 px-2 py-1 text-[11px] text-mute">
              {slotCaption(slot.slot_id)}
            </span>
          </div>
        ))}
        <div
          className="mt-5 flex items-center gap-2 rounded-xl px-4 py-3 text-[13px] font-semibold"
          style={{ background: `${theme.primary_color}14`, color: theme.primary_color }}
        >
          <CalendarCheck size={16} weight="fill" />
          {output.article.cta}
        </div>
      </div>
    </div>
  );
}
