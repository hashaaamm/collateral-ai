import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { getToken } from "@/lib/auth";

// Typed client generated from the backend OpenAPI schema (`pnpm gen:api`).
// Vite exposes build-time env as import.meta.env.VITE_*.
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  credentials: "include",
});

// Attach the DRF token to every request when the user is logged in.
const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Token ${token}`);
    return request;
  },
};

api.use(authMiddleware);
