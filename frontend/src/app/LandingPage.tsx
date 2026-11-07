import {
  ArrowRight,
  Boxes,
  Braces,
  Database,
  GitBranch,
  Layers,
  Network,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";

const features = [
  {
    icon: GitBranch,
    title: "Real dependency graph",
    body: "Parsed imports and inferred calls become a directed graph you can traverse both ways, with confidence on every edge.",
  },
  {
    icon: ShieldAlertIcon,
    title: "Evidence-backed risk",
    body: "Weighted signals for centrality, complexity, change history and test presence. Missing signals are excluded, never invented.",
  },
  {
    icon: Sparkles,
    title: "Specialised agents",
    body: "A mapper, bug investigator, risk analyst, architecture reviewer and review planner with distinct contracts.",
  },
  {
    icon: Braces,
    title: "Code intelligence",
    body: "Python uses its standard AST; JavaScript, TypeScript and Java use a documented lexer with honest coverage reporting.",
  },
  {
    icon: Database,
    title: "Durable jobs",
    body: "Indexing and investigations run as background jobs with progress, retries and explicit failure states.",
  },
  {
    icon: Terminal,
    title: "MCP access",
    body: "Read-only MCP tools expose repository overview, dependency chains, risk and investigations to any MCP client.",
  },
];

function ShieldAlertIcon(props: { className?: string }) {
  return <ShieldCheck {...props} />;
}

const architecture = [
  ["Frontend", "React · TypeScript · React Flow"],
  ["API", "FastAPI · Pydantic · SQLAlchemy"],
  ["Workers", "Durable job queue"],
  ["Analysis", "AST / lexer · NetworkX"],
  ["Agents", "Orchestrator · validated outputs"],
  ["Access", "REST · SSE · MCP"],
];

export function LandingPage() {
  const { status } = useAuthStore();
  const primary = status === "authenticated" ? "/app" : "/register";

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent">
            <Boxes className="size-4" aria-hidden />
          </span>
          <span className="text-lg font-semibold tracking-tight">NEXUS</span>
        </div>
        <nav className="flex items-center gap-4 text-sm">
          {status === "authenticated" ? (
            <Link className="rounded-lg bg-accent px-3 py-1.5 font-medium text-ink" to="/app">
              Open workspace
            </Link>
          ) : (
            <>
              <Link to="/login" className="text-muted hover:text-text">
                Sign in
              </Link>
              <Link className="rounded-lg bg-accent px-3 py-1.5 font-medium text-ink" to="/register">
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl gap-10 px-6 pb-16 pt-10 lg:grid-cols-[1.15fr_0.85fr] lg:pt-16">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
              <span className="size-1.5 rounded-full bg-ok" aria-hidden />
              Autonomous engineering intelligence · Kiroween 2026
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
              Understand your codebase.
              <br />
              Investigate problems.
              <br />
              <span className="text-accent">See the evidence.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
              NEXUS connects a real repository to a dependency graph, a transparent risk engine and
              specialised agents. Every claim points at a file and line, and unavailable data is
              shown as unavailable.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to={primary}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-ink"
              >
                {status === "authenticated" ? "Open workspace" : "Start with a public repository"}
                <ArrowRight className="size-4" aria-hidden />
              </Link>
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2.5 text-sm text-muted hover:text-text"
              >
                Public GitHub repositories only
              </a>
            </div>
            <dl className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Languages", "Python · JS · TS · Java"],
                ["Analysis", "Static only, never executed"],
                ["Agents", "5 distinct roles"],
                ["Cost", "No paid API required"],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[11px] uppercase tracking-wider text-muted">{label}</dt>
                  <dd className="mt-1 text-sm">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="rounded-2xl border border-line bg-surface/70 p-4">
            <div className="flex items-center justify-between border-b border-line pb-2 text-xs text-muted">
              <span>nexus · pipeline</span>
              <span className="flex gap-1">
                <span className="size-2 rounded-full bg-fail/60" />
                <span className="size-2 rounded-full bg-warn/60" />
                <span className="size-2 rounded-full bg-ok/60" />
              </span>
            </div>
            <div className="mt-4 space-y-2 font-mono text-[12px] leading-6">
              {[
                ["import", "github.com/owner/repository", "ok"],
                ["snapshot", "commit 9f2c1ab · branch main", "ok"],
                ["parse", "42 files · 2 parser modes", "ok"],
                ["graph", "IMPORTS 31 · CALLS 14 · TESTS 6", "ok"],
                ["risk", "5 signals · 2 available", "warn"],
                ["agents", "mapper → investigator → planner", "ok"],
              ].map(([step, detail, tone]) => (
                <div key={step} className="flex items-start gap-3">
                  <span className="w-16 shrink-0 text-muted">{step}</span>
                  <span className="w-2 shrink-0">
                    <span
                      className={
                        tone === "warn" ? "text-warn" : "text-ok"
                      }
                    >
                      ●
                    </span>
                  </span>
                  <span className="min-w-0 text-text/80">{detail}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
              Example pipeline stages. The application shows only live results from your own
              indexed repositories.
            </p>
          </div>
        </section>

        <section className="border-y border-line bg-surface/30 py-14">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-muted">
              What is actually implemented
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => (
                <div key={feature.title} className="rounded-xl border border-line bg-surface/60 p-5">
                  <feature.icon className="size-5 text-accent" aria-hidden />
                  <h3 className="mt-3 font-medium">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{feature.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-14">
          <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">How the system fits together</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted">
                The browser only talks to the versioned REST API. Indexing and investigations run in
                a worker with durable state. The MCP server calls the same authorised API rather than
                duplicating business logic.
              </p>
              <div className="mt-6 space-y-2 text-sm">
                {architecture.map(([layer, detail]) => (
                  <div key={layer} className="flex items-start gap-3 rounded-lg border border-line px-3 py-2">
                    <Layers className="mt-0.5 size-4 text-accent" aria-hidden />
                    <span className="w-20 shrink-0 font-medium">{layer}</span>
                    <span className="text-muted">{detail}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-line bg-surface/60 p-6">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Network className="size-4 text-accent" aria-hidden />
                Evidence policy
              </div>
              <ul className="mt-4 space-y-3 text-sm text-muted">
                <li>Static analysis only — imported code is never executed.</li>
                <li>Parser coverage is reported per mode: AST or lexer.</li>
                <li>Every finding states what, where, why, evidence and confidence.</li>
                <li>Inferred edges carry confidence below 1.0 and are labelled.</li>
                <li>Missing signals renormalise risk weights instead of faking values.</li>
                <li>AI output is optional, schema-validated and marked as a suggestion.</li>
              </ul>
              <div className="mt-5 rounded-lg border border-line bg-ink/50 p-3 text-xs text-muted">
                Private repositories, write actions and code execution are explicitly out of scope for
                this release.
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line py-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>NEXUS · Autonomous Engineering Intelligence Network</span>
          <span>MIT licensed · built with Kiro specs and steering</span>
        </div>
      </footer>
    </div>
  );
}
