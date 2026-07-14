import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type Company = components["schemas"]["Company"];

export function useCompanies(search?: string) {
  const q = search?.trim() ?? "";
  return useQuery({
    queryKey: ["companies", { search: q }],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/", {
        params: q ? { query: { search: q } } : {},
      });
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
        // The generated schema reuses the full `Company` response entity (incl.
        // readonly server-set fields) as the request body type since DRF's
        // OpenAPI generator doesn't emit a separate writable request schema
        // for this operation. Cast to the actual generated request-body type.
        body: body as components["schemas"]["Company"],
      });
      if (error || !data) throw new Error("create_failed");
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

type CompanyWrite = {
  name?: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors?: string[];
  logo?: string;
};

export function useUpdateCompany(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CompanyWrite) => {
      const { data, error } = await api.PATCH("/api/companies/{id}/", {
        params: { path: { id } },
        body: body as components["schemas"]["PatchedCompany"],
      });
      if (error || !data) throw new Error("update_failed");
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["companies", id] });
    },
  });
}

export function useDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/companies/{id}/", {
        params: { path: { id } },
      });
      if (error) throw new Error("delete_failed");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

/**
 * Request a signed upload URL for `file`, PUT the bytes straight to GCS, and
 * return the stored object path. The file never passes through our backend.
 */
export async function requestUploadAndPut(file: File): Promise<string> {
  const result = await api.POST("/api/companies/logo-upload-url/", {
    // The schema now types content_type as the allowed-MIME-types enum; the
    // browser's File.type is a plain string, so cast (server still validates).
    body: {
      filename: file.name,
      content_type: file.type as components["schemas"]["LogoUploadUrlRequest"]["content_type"],
    },
  });
  // Read `status` off the un-narrowed result first: this operation's schema
  // declares no error response, so narrowing on `error`/`data` collapses the
  // union to `never` (see the same pattern in auth.ts's useLogin).
  const status = result.response?.status;
  const { data, error } = result;
  if (error || !data) {
    throw new Error(status === 503 ? "upload_not_configured" : "upload_failed");
  }
  const put = await fetch(data.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!put.ok) throw new Error("upload_failed");
  return data.object_path;
}
