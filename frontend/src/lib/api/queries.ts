import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

/**
 * Example typed TanStack Query hooks built on the generated openapi-fetch client.
 * Replace the paths below with real endpoints from your schema; types flow through
 * automatically once `pnpm gen:api` has produced ./schema.d.ts.
 */

export function useCurrentUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/users/me/");
      if (error) throw error;
      return data;
    },
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  // `me` is read-only; updates go to /api/users/{id}/ (DRF UpdateModelMixin). The viewset scopes
  // the queryset to the current user, so only your own record is editable.
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: number } & Record<string, unknown>) => {
      const { data, error } = await api.PATCH("/api/users/{id}/", {
        params: { path: { id } },
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}
