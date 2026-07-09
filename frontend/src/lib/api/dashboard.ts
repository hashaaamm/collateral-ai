import { useQuery } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type DashboardStats = components["schemas"]["DashboardStats"];

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const { data, error } = await api.GET("/api/dashboard/stats/", {});
  if (error || !data) throw error ?? new Error("dashboard_stats_failed");
  return data;
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });
}
