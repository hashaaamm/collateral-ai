import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type Company = components["schemas"]["Company"];

export function useCompanies() {
  return useQuery({
    queryKey: ["companies"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/");
      if (error) throw error;
      return data;
    },
  });
}

export function useCompany(id: number) {
  return useQuery({
    queryKey: ["companies", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/{id}/", {
        params: { path: { id } },
      });
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      name: string;
      website?: string;
      industry?: string;
      description?: string;
      brand_colors?: string[];
      logo?: string;
    }) => {
      const { data, error } = await api.POST("/api/companies/", {
        body: body as components["schemas"]["Company"],
      });
      if (error || !data) throw new Error("create_failed");
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

/**
 * Request a signed upload URL for `file`, PUT the bytes straight to GCS, and
 * return the stored object path. The file never passes through our backend.
 */
export async function requestUploadAndPut(file: File): Promise<string> {
  type Result = Awaited<ReturnType<typeof api.POST>>;
  const result: Result = await api.POST("/api/companies/logo-upload-url/", {
    body: { filename: file.name, content_type: file.type },
  } as never);
  const { data, error, response } = result;
  if (error || !data) {
    throw new Error((response as { status?: number } | undefined)?.status === 503 ? "upload_not_configured" : "upload_failed");
  }
  const put = await fetch(data.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!put.ok) throw new Error("upload_failed");
  return data.object_path;
}
