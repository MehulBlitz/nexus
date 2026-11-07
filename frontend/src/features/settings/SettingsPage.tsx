import { Copy, KeyRound, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
import { useApiTokens, useDashboard } from "@/hooks/queries";
import { useAuthStore } from "@/stores/auth";
import { SystemStatus } from "@/features/dashboard/SystemStatus";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  formatDate,
  inputClass,
} from "@/components/ui";

const passwordSchema = z
  .object({
    current: z.string().min(1, "Current password is required"),
    next: z.string().min(10, "New password must be at least 10 characters"),
    confirm: z.string(),
  })
  .refine((value) => value.next === value.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

export function SettingsPage() {
  const { user, clear } = useAuthStore();
  const dashboard = useDashboard();
  const tokens = useApiTokens(true);
  const client = useQueryClient();
  const navigate = useNavigate();
  const [tokenName, setTokenName] = useState("");
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeId, setRevokeId] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [nextPassword, setNextPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<Record<string, string>>({});
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);

  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const createToken = useMutation({
    mutationFn: () => api.auth.createToken(tokenName),
    onSuccess: (result) => {
      setCreatedToken(result.token);
      setTokenName("");
      void client.invalidateQueries({ queryKey: ["tokens"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.auth.revokeToken(id),
    onSuccess: () => {
      setRevokeId(null);
      void client.invalidateQueries({ queryKey: ["tokens"] });
    },
  });

  const changePassword = useMutation({
    mutationFn: (input: { current: string; next: string }) =>
      api.auth.changePassword(input.current, input.next),
    onSuccess: () => {
      setCurrentPassword("");
      setNextPassword("");
      setConfirmPassword("");
      setPasswordMessage("Password changed. Other sessions were revoked.");
    },
  });

  const deleteAccount = useMutation({
    mutationFn: () => api.auth.deleteAccount(deletePassword),
    onSuccess: () => {
      clear();
      client.clear();
      navigate("/");
    },
    onError: (error) => setDeleteError(error.message),
  });

  const submitPassword = (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordMessage(null);
    const parsed = passwordSchema.safeParse({
      current: currentPassword,
      next: nextPassword,
      confirm: confirmPassword,
    });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = issue.message;
      setPasswordErrors(next);
      return;
    }
    setPasswordErrors({});
    changePassword.mutate({ current: currentPassword, next: nextPassword });
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted">Profile, API access, inference status and account security.</p>
      </header>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardTitle>Profile</CardTitle>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Display name</dt>
              <dd>{user?.display_name ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Email</dt>
              <dd className="truncate">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Account created</dt>
              <dd>{formatDate(user?.created_at)}</dd>
            </div>
          </dl>
          <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
            Email verification is only available when an email provider is configured. No default or
            shared administrator account exists.
          </p>
        </Card>

        <Card>
          <CardTitle>Inference provider</CardTitle>
          {dashboard.isLoading ? (
            <Loading label="Checking provider…" />
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Badge tone={dashboard.data?.ai_configured ? "accent" : "neutral"}>
                  {dashboard.data?.ai_configured ? dashboard.data.ai_provider : "deterministic fallback"}
                </Badge>
                <span className="text-xs text-muted">
                  {dashboard.data?.ai_configured
                    ? "LLM reasoning is enabled for agents that support it."
                    : "No LLM is configured; analysis and investigations remain fully functional."}
                </span>
              </div>
              <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-ink/60 p-3 font-mono text-[11px] text-muted">{`AI_PROVIDER=${dashboard.data?.ai_configured ? dashboard.data.ai_provider : "none"}
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=<your-model>`}</pre>
              <p className="mt-2 text-xs text-muted">
                Configure these on the backend environment. Repository source is never sent to a
                provider unless you explicitly enable one, and outputs are schema-validated.
              </p>
            </>
          )}
        </Card>
      </div>

      <Card>
        <CardTitle>System status</CardTitle>
        <SystemStatus />
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardTitle>API tokens</CardTitle>
          <form
            className="flex items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (tokenName.trim().length < 2) return;
              createToken.mutate();
            }}
          >
            <div className="flex-1">
              <Field label="Token name" htmlFor="token-name" hint="Used by the MCP server and scripts">
                <input
                  id="token-name"
                  className={inputClass}
                  value={tokenName}
                  onChange={(event) => setTokenName(event.target.value)}
                  placeholder="MCP client"
                />
              </Field>
            </div>
            <Button type="submit" disabled={createToken.isPending || tokenName.trim().length < 2}>
              {createToken.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <KeyRound className="size-4" aria-hidden />}
              Create
            </Button>
          </form>
          {createToken.isError ? <div className="mt-3"><ErrorState message={createToken.error.message} /></div> : null}
          {createdToken ? (
            <div className="mt-3 rounded-lg border border-warn/40 bg-warn/5 p-3">
              <p className="text-xs font-medium text-warn">Copy this token now. It is not shown again.</p>
              <div className="mt-2 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-ink/70 p-2 font-mono text-xs">{createdToken}</code>
                <Button
                  variant="secondary"
                  className="px-2 py-1 text-xs"
                  onClick={() => {
                    void navigator.clipboard.writeText(createdToken).then(() => {
                      setCopied(true);
                      setTimeout(() => setCopied(false), 1500);
                    });
                  }}
                >
                  <Copy className="size-3.5" aria-hidden /> {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          ) : null}

          <div className="mt-4 border-t border-line pt-3">
            {tokens.isLoading ? (
              <Loading label="Loading tokens…" />
            ) : tokens.isError ? (
              <ErrorState message={tokens.error.message} />
            ) : (tokens.data?.length ?? 0) === 0 ? (
              <EmptyState icon={KeyRound} title="No API tokens">
                Create a scoped token for read-only MCP access.
              </EmptyState>
            ) : (
              <ul className="divide-y divide-line">
                {tokens.data!.map((token) => (
                  <li key={token.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{token.name}</p>
                      <p className="font-mono text-xs text-muted">
                        {token.prefix}… · {token.scope} · created {formatDate(token.created_at)}
                      </p>
                      <p className="text-xs text-muted">
                        last used {token.last_used_at ? formatDate(token.last_used_at) : "never"}
                      </p>
                    </div>
                    {revokeId === token.id ? (
                      <span className="flex shrink-0 items-center gap-1">
                        <Button variant="danger" className="px-2 py-1 text-xs" onClick={() => revoke.mutate(token.id)}>
                          Confirm
                        </Button>
                        <Button variant="ghost" className="px-1 py-1 text-xs" onClick={() => setRevokeId(null)}>
                          Cancel
                        </Button>
                      </span>
                    ) : (
                      <Button variant="ghost" className="shrink-0 px-2 py-1 text-xs" onClick={() => setRevokeId(token.id)}>
                        <Trash2 className="size-3.5" aria-hidden /> Revoke
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <Card>
          <CardTitle>Change password</CardTitle>
          <form onSubmit={submitPassword} className="space-y-3" noValidate>
            <Field label="Current password" htmlFor="current-password" error={passwordErrors.current}>
              <input
                id="current-password"
                type="password"
                className={inputClass}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                autoComplete="current-password"
              />
            </Field>
            <Field label="New password" htmlFor="new-password" error={passwordErrors.next}>
              <input
                id="new-password"
                type="password"
                className={inputClass}
                value={nextPassword}
                onChange={(event) => setNextPassword(event.target.value)}
                autoComplete="new-password"
              />
            </Field>
            <Field label="Confirm new password" htmlFor="confirm-password" error={passwordErrors.confirm}>
              <input
                id="confirm-password"
                type="password"
                className={inputClass}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
              />
            </Field>
            {changePassword.isError ? <ErrorState message={changePassword.error.message} /> : null}
            {passwordMessage ? <p className="text-xs text-ok">{passwordMessage}</p> : null}
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <ShieldCheck className="size-4" aria-hidden />}
              Update password
            </Button>
          </form>
        </Card>
      </div>

      <Card className="border-fail/30">
        <CardTitle>Delete account</CardTitle>
        <p className="text-sm text-muted">
          Deletes your account, sessions, tokens, repositories, snapshots, analyses and reports. This
          cannot be undone.
        </p>
        <form
          className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            setDeleteError(null);
            if (deleteConfirm !== "DELETE") {
              setDeleteError('Type DELETE to confirm');
              return;
            }
            deleteAccount.mutate();
          }}
        >
          <Field label="Password" htmlFor="delete-password">
            <input
              id="delete-password"
              type="password"
              className={inputClass}
              value={deletePassword}
              onChange={(event) => setDeletePassword(event.target.value)}
              autoComplete="current-password"
            />
          </Field>
          <Field label="Type DELETE" htmlFor="delete-confirm">
            <input
              id="delete-confirm"
              className={inputClass}
              value={deleteConfirm}
              onChange={(event) => setDeleteConfirm(event.target.value)}
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit" variant="danger" disabled={deleteAccount.isPending}>
              Delete account
            </Button>
          </div>
        </form>
        {deleteError ? <p className="mt-2 text-xs text-fail">{deleteError}</p> : null}
        {deleteAccount.isError ? <p className="mt-2 text-xs text-fail">{deleteAccount.error.message}</p> : null}
      </Card>
    </div>
  );
}
