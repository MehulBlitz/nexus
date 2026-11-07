import { Boxes, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import { Button, Field, inputClass } from "@/components/ui";
import { useAuthStore } from "@/stores/auth";
import { queryKeys } from "@/hooks/queries";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

const registerSchema = loginSchema.extend({
  displayName: z.string().min(2, "Name must be at least 2 characters").max(80),
  password: z.string().min(10, "Password must be at least 10 characters"),
});

type Mode = "login" | "register";

export function AuthPage({ mode }: { mode: Mode }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const { setUser } = useAuthStore();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setServerError(null);
    const parsed =
      mode === "login"
        ? loginSchema.safeParse({ email, password })
        : registerSchema.safeParse({ email, password, displayName });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] === "displayName" ? "displayName" : String(issue.path[0]);
        next[key] = issue.message;
      }
      setErrors(next);
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      const result =
        mode === "login"
          ? await api.auth.login(email, password)
          : await api.auth.register(email, password, displayName);
      setUser(result.user);
      client.setQueryData(queryKeys.me, result.user);
      const redirect = (location.state as { from?: string } | null)?.from ?? "/app";
      navigate(redirect, { replace: true });
    } catch (error) {
      setServerError(
        error instanceof ApiError
          ? error.status === 409
            ? "An account with this email already exists. Sign in instead."
            : error.message
          : "Unexpected error",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <Link to="/" className="mb-8 flex items-center gap-2 self-start">
        <span className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent">
          <Boxes className="size-4" aria-hidden />
        </span>
        <span className="text-lg font-semibold tracking-tight">NEXUS</span>
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight">
        {mode === "login" ? "Sign in" : "Create your workspace"}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {mode === "login"
          ? "Continue to your repositories, graph and investigations."
          : "NEXUS works with public GitHub repositories. No paid AI key is required."}
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {mode === "register" ? (
          <Field label="Display name" htmlFor="displayName" error={errors.displayName}>
            <input
              id="displayName"
              className={inputClass}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
              aria-invalid={Boolean(errors.displayName)}
            />
          </Field>
        ) : null}
        <Field label="Email" htmlFor="email" error={errors.email}>
          <input
            id="email"
            type="email"
            className={inputClass}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
          />
        </Field>
        <Field
          label="Password"
          htmlFor="password"
          error={errors.password}
          hint={mode === "register" ? "At least 10 characters." : undefined}
        >
          <input
            id="password"
            type="password"
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            aria-invalid={Boolean(errors.password)}
          />
        </Field>

        {serverError ? (
          <p className="rounded-lg border border-fail/30 bg-fail/5 p-3 text-sm text-fail" role="alert">
            {serverError}
          </p>
        ) : null}

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted">
        {mode === "login" ? (
          <>
            No account yet?{" "}
            <Link to="/register" className="text-accent hover:underline">
              Create one
            </Link>
          </>
        ) : (
          <>
            Already registered?{" "}
            <Link to="/login" className="text-accent hover:underline">
              Sign in
            </Link>
          </>
        )}
      </p>
      <p className="mt-8 text-xs leading-relaxed text-muted">
        Sessions use HTTP-only, SameSite cookies. Mutating requests require a CSRF token. Account
        deletion and API tokens are managed in Settings.
      </p>
    </main>
  );
}
