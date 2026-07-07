import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";
import { putWithProgress } from "./upload";

export type Document = components["schemas"]["Document"];

export function useDocuments(companyId: number) {
  return useQuery({
    queryKey: ["documents", companyId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/{company_pk}/documents/", {
        params: { path: { company_pk: companyId } },
      });
      if (error) throw error;
      return data;
    },
    refetchInterval: (query) =>
      (query.state.data ?? []).some((d) => d.status === "processing") ? 3000 : false,
  });
}

export async function uploadDocument({
  companyId,
  file,
  onProgress,
}: {
  companyId: number;
  file: File;
  onProgress: (pct: number) => void;
}): Promise<Document> {
  const created = await api.POST("/api/companies/{company_pk}/documents/", {
    params: { path: { company_pk: companyId } },
    body: { file_name: file.name, content_type: file.type },
  });
  const createStatus = created.response?.status;
  if (created.error || !created.data) {
    throw new Error(createStatus === 503 ? "upload_not_configured" : "upload_failed");
  }
  await putWithProgress(created.data.upload_url, file, onProgress);
  const done = await api.POST("/api/companies/{company_pk}/documents/{id}/complete/", {
    params: { path: { company_pk: companyId, id: created.data.id } },
  });
  if (done.error || !done.data) throw new Error("complete_failed");
  return done.data as Document;
}

export function useCompleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, companyId }: { id: number; companyId: number }) => {
      const { data, error } = await api.POST(
        "/api/companies/{company_pk}/documents/{id}/complete/",
        { params: { path: { company_pk: companyId, id } } },
      );
      if (error || !data) throw new Error("complete_failed");
      return data as Document;
    },
    onSuccess: (_data, { companyId }) =>
      qc.invalidateQueries({ queryKey: ["documents", companyId] }),
  });
}
