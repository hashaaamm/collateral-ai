import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  EnvelopeSimple,
  Eye,
  EyeSlash,
  LockSimple,
  Stack,
} from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loginSchema, useLogin, type LoginValues } from "@/lib/api/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => navigate({ to: "/dashboard" }),
    });
  });

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[radial-gradient(120%_120%_at_50%_0%,#eeeefb_0%,#f6f6f8_55%)] p-6">
      <div className="w-full max-w-[400px]">
        {/* Logo lockup */}
        <div className="mb-[30px] flex items-center justify-center gap-[11px]">
          <div className="flex size-[34px] items-center justify-center rounded-[9px] bg-brand shadow-[0_4px_12px_rgba(91,91,214,0.35)]">
            <Stack weight="fill" size={19} className="text-white" />
          </div>
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">
            Collateral AI
          </span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-hairline bg-surface p-8 shadow-login">
          <h1 className="mb-1 text-[21px] font-bold tracking-[-0.02em] text-ink">
            Welcome back
          </h1>
          <p className="mb-6 text-sm text-subtext">
            Sign in to your marketing studio
          </p>

          <form onSubmit={onSubmit} noValidate>
            {/* Email */}
            <label
              htmlFor="email"
              className="mb-[7px] block text-[12.5px] font-semibold text-body"
            >
              Email
            </label>
            <div className="flex items-center gap-[9px] rounded-[10px] border border-field bg-subtle px-3">
              <EnvelopeSimple size={16} className="text-mute" />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                className="h-auto border-0 bg-transparent px-0 py-[11px] text-sm shadow-none focus-visible:ring-0"
                {...register("email")}
              />
            </div>
            <p className="mt-1 min-h-[16px] text-xs text-destructive">
              {errors.email?.message ?? ""}
            </p>

            {/* Password */}
            <label
              htmlFor="password"
              className="mb-[7px] block text-[12.5px] font-semibold text-body"
            >
              Password
            </label>
            <div className="flex items-center gap-[9px] rounded-[10px] border border-field bg-subtle px-3">
              <LockSimple size={16} className="text-mute" />
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                className="h-auto border-0 bg-transparent px-0 py-[11px] text-sm shadow-none focus-visible:ring-0"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="text-mute"
              >
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="mt-1 min-h-[16px] text-xs text-destructive">
              {errors.password?.message ?? ""}
            </p>

            {/* Server error */}
            {login.isError && (
              <p className="mb-3 text-sm text-destructive">
                Incorrect email or password
              </p>
            )}

            <Button
              type="submit"
              disabled={login.isPending}
              className="mt-1 flex h-auto w-full items-center justify-center gap-2 rounded-[10px] bg-brand py-3 text-[14.5px] font-semibold text-white hover:bg-brand-hover"
            >
              {login.isPending ? (
                "Signing in…"
              ) : (
                <>
                  Sign in <ArrowRight weight="bold" size={15} />
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
