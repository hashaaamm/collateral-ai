import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type Template = components["schemas"]["Template"];

export type TemplateConstraints = {
  headline_max_words: number;
  subheadline_max_words: number;
  body_section_count: number;
  body_section_max_words: number;
  cta_max_words: number;
};

export type TemplateImageSlot = {
  slot_id: string;
  label: string;
  spec: string;
  source: "sender" | "receiver" | "generated_placeholder";
};

/** constraints/image_slots are loose JSON fields in the schema; cast through the contract. */
export function templateConstraints(t: Template): TemplateConstraints {
  return t.constraints as TemplateConstraints;
}

export function templateImageSlots(t: Template): TemplateImageSlot[] {
  return (t.image_slots ?? []) as TemplateImageSlot[];
}

export type TemplateWrite = {
  name: string;
  description?: string;
  constraints: TemplateConstraints;
  image_slots: TemplateImageSlot[] | [];
  theme: { primary_color: string; accent_color: string };
};

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/templates/");
      if (error) throw error;
      return data;
    },
  });
}

export async function createTemplate(body: TemplateWrite): Promise<Template> {
  const { data, error } = await api.POST("/api/templates/", {
    // Same cast pattern as companies.ts: DRF's schema reuses the response
    // entity as the request body type.
    body: body as unknown as Template,
  });
  if (error || !data) throw error ?? new Error("create_failed");
  return data;
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
