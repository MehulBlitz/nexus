import { SystemStatus } from "@/features/dashboard/SystemStatus";

export function App() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:py-20">
      <header className="mb-10">
        <h1 className="text-4xl font-semibold tracking-tight">NEXUS</h1>
        <p className="mt-3 max-w-xl text-lg text-muted">
          Understand your codebase, investigate problems, and see engineering risk with the evidence
          behind it.
        </p>
      </header>

      <SystemStatus />

      <p className="mt-6 max-w-xl text-sm text-muted">
        This is the foundation build. Sign-in, repository import, the dependency graph, risk
        analysis, and investigations are not available yet and will appear here as they ship.
      </p>
    </main>
  );
}
