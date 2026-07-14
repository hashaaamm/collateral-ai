import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type MaterialList = components["schemas"]["MaterialList"];
export type MaterialDetail = components["schemas"]["MaterialDetail"];

/** The output JSON contract (spec §4). output_json is loose JSON in the schema. */
export type OutputJson = {
  template_id: string;
  theme: { primary_color: string; accent_color: string };
  article: {
    headline: string;
    subheadline: string;
    body_sections: { title: string; text: string }[];
    cta: string;
    cta_url?: string;
  };
  image_slots: { slot_id: string; description: string; source: string }[];
  source_references: { source_id: string; used_fact: string }[];
};

export type ValidationResultJson = {
  is_valid: boolean;
  errors: { category: string; message: string }[];
};

export function outputJson(m: MaterialDetail): OutputJson | null {
  return (m.output_json as OutputJson | null) ?? null;
}

export function validationResult(m: MaterialDetail): ValidationResultJson | null {
  return (m.validation_result as ValidationResultJson | null) ?? null;
}

// `generation_status` is optional in the generated schema (DRF field default
// makes it non-required on the response contract), so accept it as optional here.
export function isGenerating(m: { generation_status?: string }): boolean {
  return m.generation_status === "queued" || m.generation_status === "processing";
}

export type MaterialFilters = {
  company?: number;
  sender?: number;
  receiver?: number;
  generation_status?: string;
  review_status?: string;
  search?: string;
};

export function useMaterials(filters: MaterialFilters = {}) {
  return useQuery({
    queryKey: ["materials", filters],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/materials/", {
        params: { query: filters },
      });
      if (error) throw error;
      return data;
    },
    // Poll while anything is generating; stop on terminal states (spec §7.2).
    refetchInterval: (query) =>
      (query.state.data ?? []).some(isGenerating) ? 3000 : false,
  });
}

export function useMaterial(id: number) {
  return useQuery({
    queryKey: ["materials", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/materials/{id}/", {
        params: { path: { id } },
      });
      if (error) throw error;
      return data;
    },
    refetchInterval: (query) => {
      const material = query.state.data;
      return material && isGenerating(material) ? 3000 : false;
    },
  });
}

export type MaterialCreateBody = {
  title: string;
  description?: string;
  sender_company: number;
  receiver_company: number;
  template: number;
  prompt: string;
  tone?: string;
  cta_style?: string;
  cta_link?: string;
  language?: string;
};

export async function createMaterial(body: MaterialCreateBody): Promise<MaterialDetail> {
  const { data, error } = await api.POST("/api/materials/", {
    body: body as unknown as components["schemas"]["MaterialCreate"],
  });
  // Throw the DRF error body itself so the wizard can show field errors.
  if (error || !data) throw error ?? new Error("create_failed");
  return data as MaterialDetail;
}

export function useCreateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createMaterial,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

export type MaterialUpdateBody = {
  title?: string;
  description?: string;
  prompt?: string;
  review_status?: "pending" | "approved" | "rejected";
};

export function useUpdateMaterial(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: MaterialUpdateBody) => {
      const { data, error } = await api.PATCH("/api/materials/{id}/", {
        params: { path: { id } },
        body: body as components["schemas"]["PatchedMaterialUpdate"],
      });
      if (error || !data) throw error ?? new Error("update_failed");
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["materials"] });
      qc.invalidateQueries({ queryKey: ["materials", id] });
    },
  });
}

export async function regenerateMaterial(
  id: number,
  prompt?: string,
): Promise<MaterialDetail> {
  const { data, error } = await api.POST("/api/materials/{id}/regenerate/", {
    params: { path: { id } },
    // Omit the body when the prompt is unchanged so we re-run with the stored one.
    ...(prompt !== undefined ? { body: { prompt } } : {}),
  });
  if (error || !data) throw error ?? new Error("regenerate_failed");
  return data as MaterialDetail;
}

export function useRegenerateMaterial(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prompt?: string) => regenerateMaterial(id, prompt),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["materials"] });
      qc.invalidateQueries({ queryKey: ["materials", id] });
    },
  });
}

export async function deleteMaterial(id: number): Promise<void> {
  const { error } = await api.DELETE("/api/materials/{id}/", {
    params: { path: { id } },
  });
  if (error) throw new Error("delete_failed");
}

export function useDeleteMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

/** DRF error body → first human-readable message (for the wizard). */
export function createMaterialErrorText(err: unknown): string {
  if (err && typeof err === "object") {
    for (const value of Object.values(err as Record<string, unknown>)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0]);
      if (typeof value === "string") return value;
    }
  }
  return "Something went wrong. Please try again.";
}
