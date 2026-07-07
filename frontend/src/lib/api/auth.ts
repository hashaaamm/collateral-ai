import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import type { components } from "./schema";
import { api } from "./client";
import { setToken } from "@/lib/auth";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

export type LoginValues = z.infer<typeof loginSchema>;

/**
 * Log in via DRF's obtain_auth_token. The backend field is named `username`
 * but resolves against the email (USERNAME_FIELD = "email"). On success the
 * token is persisted; failure rejects so the form can show an inline error.
 */
export function useLogin() {
  return useMutation({
    mutationFn: async ({ email, password }: LoginValues) => {
      async function post() {
        try {
          return await api.POST("/api/auth-token/", {
            // drf-spectacular lists the readonly `token` on the request
            // body; we only send username + password. AuthToken is
            // assignable to this narrower shape, so the cast is safe.
            body: {
              username: email,
              password,
            } as components["schemas"]["AuthToken"],
          });
        } catch {
          throw new Error("network_error");
        }
      }
      const result = await post();
      const status = result.response.status;
      const { data, error } = result;
      if (error || !data) {
        throw new Error(
          status === 400 ? "invalid_credentials" : "network_error",
        );
      }
      setToken(data.token);
      return data;
    },
  });
}
