import { expect, test } from "@playwright/test";

/**
 * Mandatory Core Release 1 scenario.
 *
 * Requires a running backend and a public demo repository with supported source files:
 *
 *   E2E_BASE_URL=http://127.0.0.1:5173 \
 *   E2E_REPO_URL=https://github.com/your-org/your-demo \
 *   npx playwright install chromium && npx playwright test
 *
 * Without E2E_REPO_URL the scenario is skipped rather than pointed at a fabricated repository.
 */
const repoUrl = process.env.E2E_REPO_URL;

test.describe("import → graph → risk → investigation → report", () => {
  test.skip(!repoUrl, "Set E2E_REPO_URL to a public demo repository to run this scenario.");

  test("a developer can investigate a repository end to end", async ({ page }) => {
    const email = `e2e-${Date.now()}@example.com`;
    const password = "e2e-password-12345";

    await page.goto("/register");
    await page.getByLabel("Display name").fill("E2E Engineer");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByRole("heading", { name: "Engineering intelligence" })).toBeVisible();

    await page.getByRole("link", { name: "Import repository" }).first().click();
    await page.getByLabel("GitHub repository URL").fill(repoUrl!);
    await page.getByRole("button", { name: "Import" }).click();
    await expect(page.getByText("Open repository")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/Indexing finished\./)).toBeVisible({ timeout: 150_000 });
    await page.getByRole("link", { name: "Open repository" }).click();

    // Indexing must finish with real data.
    await expect(page.getByText("Files indexed")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText("Parser coverage")).toBeVisible();
    await expect(page.getByText("Language distribution")).toBeVisible();

    // Graph: select a node and run impact analysis.
    await page.getByRole("link", { name: "Graph" }).click();
    await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 30_000 });
    await page.locator(".react-flow__node").first().click();
    await expect(page.getByText("Node details")).toBeVisible();
    await page.getByRole("button", { name: "Impact" }).click();
    await expect(page.getByText("Impact analysis")).toBeVisible();

    // Risk: run analysis and open a finding if one exists.
    await page.getByRole("link", { name: "Risk center" }).click();
    const runAnalysis = page.getByRole("button", { name: /Run analysis|Re-run analysis/ });
    await runAnalysis.click();
    await expect(page.getByText("Overall score")).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(/not a probability/).first()).toBeVisible();

    // Investigation: submit and wait for the agent timeline.
    await page.getByRole("link", { name: "Investigations" }).click();
    await page.getByLabel("Question").fill("Where is the highest-coupling module and what could break?");
    await page.getByRole("button", { name: "Investigate" }).click();
    await expect(page.getByText("Agent timeline")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText(/completed|failed/).first()).toBeVisible({ timeout: 150_000 });

    // Report: generate and download Markdown.
    await page.getByRole("link", { name: "Reports" }).click();
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByText(/Generated .* by NEXUS/)).toBeVisible({ timeout: 60_000 });
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download Markdown" }).click();
    expect((await download).suggestedFilename()).toMatch(/\.md$/);

    // Logout.
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
