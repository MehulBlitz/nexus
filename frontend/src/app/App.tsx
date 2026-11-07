import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useMe } from "@/hooks/queries";
import { useAuthStore } from "@/stores/auth";
import { useEffect } from "react";
import { AppLayout } from "@/app/Layout";
import { LandingPage } from "@/app/LandingPage";
import { AuthPage } from "@/app/AuthPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { RepositoriesPage } from "@/features/repositories/RepositoriesPage";
import { RepositoryWorkspace } from "@/features/repositories/RepositoryWorkspace";
import { RepositoryOverviewPage } from "@/features/repositories/RepositoryOverviewPage";
import { GraphPage } from "@/features/graph/GraphPage";
import { RiskPage } from "@/features/risks/RiskPage";
import { InvestigationsPage, InvestigationDetailPage } from "@/features/investigations/InvestigationsPage";
import { AgentsPage } from "@/features/agents/AgentsPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";

function SessionSync() {
  const me = useMe();
  const { status, setUser } = useAuthStore();
  useEffect(() => {
    if (me.isLoading) return;
    if (me.data) setUser(me.data);
    else if (me.isError || status === "unknown") setUser(null);
  }, [me.data, me.isError, me.isLoading, setUser, status]);
  return null;
}

function Protected({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isLoading) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-20 text-sm text-muted">Restoring your session…</main>
    );
  }
  if (!me.data) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <>
      <SessionSync />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route
          path="/app"
          element={
            <Protected>
              <AppLayout />
            </Protected>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="repositories" element={<RepositoriesPage />} />
          <Route path="repositories/:repositoryId" element={<RepositoryWorkspace />}>
            <Route index element={<RepositoryOverviewPage />} />
            <Route path="graph" element={<GraphPage />} />
            <Route path="risks" element={<RiskPage />} />
            <Route path="investigations" element={<InvestigationsPage />} />
            <Route path="investigations/:investigationId" element={<InvestigationDetailPage />} />
            <Route path="reports" element={<ReportsPage />} />
          </Route>
          <Route path="agents" element={<AgentsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
