import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Typed client generated from the backend OpenAPI schema (`pnpm gen:api`).
// Vite exposes build-time env as import.meta.env.VITE_*.
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  credentials: "include",
});
