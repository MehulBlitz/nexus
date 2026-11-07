import {
  Activity,
  BookOpen,
  Boxes,
  ChevronRight,
  GitBranch,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { useMe } from "@/hooks/queries";
import { Loading } from "@/components/ui";

const nav = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/repositories", label: "Repositories", icon: Boxes },
  { to: "/app/agents", label: "Agents", icon: Sparkles },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const quick = [
  { to: "/app/repositories", label: "Graph explorer", icon: GitBranch },
  { to: "/app/repositories", label: "Risk center", icon: ShieldAlert },
  { to: "/app/repositories", label: "Investigations", icon: Activity },
  { to: "/app/agents", label: "Agent history", icon: BookOpen },
];

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const me = useMe();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { setUser } = useAuthStore();
  const user = me.data ?? null;

  if (me.isLoading) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-16">
        <Loading label="Restoring your session…" />
      </main>
    );
  }
  if (me.isError || !user) {
    // A 401 is the normal signed-out state; anything else is shown on the login page.
    return <SignInRequired onNavigate={() => navigate("/login")} />;
  }

  const logout = async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
      client.clear();
      navigate("/login");
    }
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-30 w-64 border-r border-line bg-surface/95 p-4 backdrop-blur transition-transform lg:static lg:w-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between">
          <NavLink to="/app" className="flex items-center gap-2" onClick={() => setOpen(false)}>
            <span className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent">
              <Boxes className="size-4" aria-hidden />
            </span>
            <span className="text-lg font-semibold tracking-tight">NEXUS</span>
          </NavLink>
          <button
            type="button"
            className="text-muted lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav className="mt-8 space-y-1" aria-label="Main">
          {nav.map((item) => (
            <NavLink
              key={item.to + item.label}
              to={item.to}
              end={item.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                  isActive ? "bg-accent/10 text-accent" : "text-muted hover:bg-white/5 hover:text-text",
                )
              }
            >
              <item.icon className="size-4" aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <p className="mt-8 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted/70">
          Within a repository
        </p>
        <div className="mt-2 space-y-0.5">
          {quick.map((item) => (
            <span
              key={item.label}
              className="flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-xs text-muted/70"
              title="Open a repository to use this view"
            >
              <item.icon className="size-3.5" aria-hidden />
              {item.label}
            </span>
          ))}
        </div>

        <div className="absolute inset-x-4 bottom-4 rounded-lg border border-line bg-ink/60 p-3">
          <p className="truncate text-sm font-medium">{user.display_name}</p>
          <p className="truncate text-xs text-muted">{user.email}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-2 flex w-full items-center gap-2 rounded border border-line px-2 py-1.5 text-xs text-muted hover:border-fail/50 hover:text-fail"
          >
            <LogOut className="size-3.5" aria-hidden />
            Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-ink/80 px-4 py-3 backdrop-blur lg:px-8">
          <button
            type="button"
            className="text-muted lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </button>
          <div className="flex items-center gap-1 text-xs text-muted">
            <span>Workspace</span>
            <ChevronRight className="size-3" aria-hidden />
            <span className="text-text">Engineering intelligence</span>
          </div>
          <span className="ml-auto hidden rounded-md border border-line px-2 py-1 text-xs text-muted sm:block">
            {user.email}
          </span>
        </header>
        <main className="px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function SignInRequired({ onNavigate }: { onNavigate: () => void }) {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center px-6 py-24 text-center">
      <h1 className="text-2xl font-semibold">Sign in to continue</h1>
      <p className="mt-2 text-sm text-muted">
        Your session is missing or has expired. Sign in to view your repositories and
        investigations.
      </p>
      <button
        type="button"
        onClick={onNavigate}
        className="mt-6 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-ink"
      >
        Go to sign in
      </button>
    </main>
  );
}
