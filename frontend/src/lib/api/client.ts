import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { clearToken, getToken } from "@/lib/auth";

// Typed client generated from the backend OpenAPI schema (`pnpm gen:api`).
// Vite exposes build-time env as import.meta.env.VITE_*.
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  credentials: "include",
});

/**
 * Handle a rejected token: if we thought we were logged in (a token is present)
 * but the server says 401, the session is dead — drop the stale token and send
 * the user to login. Guarded on `getToken()` so an expected 401 (e.g. before
 * login) is a no-op, and on the pathname so we never loop on /login itself.
 * Exported for testing. The backend emits a genuine 401 for missing/invalid
 * tokens (see DEFAULT_AUTHENTICATION_CLASSES ordering in settings/base.py).
 */
export function enforceSession(response: Response): void {
  if (response.status !== 401 || !getToken()) return;
  clearToken();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// Attach the DRF token to every request when the user is logged in, and react
// to session loss on every response.
const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Token ${token}`);
    return request;
  },
  onResponse({ response }) {
    enforceSession(response);
    return response;
  },
};

api.use(authMiddleware);
