import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { withEdgeTestService } from "./edge-test-service.mjs";

test("Edge keeps a manual folder selection when the optional picker responds late", () =>
  withEdgeTestService(["--launcher"], async ({ directory, url, context }) => {
    const launcher = await context.newPage();
    const pickerReply = Promise.withResolvers();
    const stalePath = join(directory, "Folder from delayed picker");
    await launcher.route("**/api/choose-folder", async route => {
      await pickerReply.promise;
      await route.fulfill({ json: { folder: "stale", path: stalePath, projects: [], warnings: [] } });
    });
    await launcher.goto(url);
    const browse = launcher.getByRole("button", { name: "Browse (optional)", exact: true });
    const pathInput = launcher.getByLabel("Project folder path");
    const existingProject = launcher.getByRole("button", { name: "Open project Existing local project" });

    try {
      const requestStarted = launcher.waitForRequest("**/api/choose-folder");
      await browse.click();
      await requestStarted;
      assert.equal(await pathInput.isEnabled(), true);
      await pathInput.fill(`"${directory}"`);
      await launcher.getByRole("button", { name: "Use folder" }).click();
      await existingProject.waitFor();
      const selectedPath = await pathInput.inputValue();

      pickerReply.resolve();
      await browse.waitFor();
      assert.equal(await browse.isEnabled(), true);
      assert.equal(await pathInput.inputValue(), selectedPath);
      assert.equal(await existingProject.isVisible(), true);
      assert.equal(await launcher.getByText(stalePath, { exact: true }).count(), 0);
    } finally {
      pickerReply.resolve();
    }
  }));

test("Edge opens projects and saves a CSV using manual folder selection when Tk is unavailable", () =>
  withEdgeTestService(["--launcher"], async ({ directory, url, openApp, openProject, openModule, closeProject }) => {
    const launcher = await openApp(url);
    const pathInput = launcher.getByLabel("Project folder path");
    const select = launcher.getByRole("button", { name: "Use folder" });
    const browse = launcher.getByRole("button", { name: "Browse (optional)" });

    await browse.click();
    await launcher.getByRole("alert").filter({ hasText: "Paste a local path" }).waitFor();
    assert.equal(await pathInput.isEnabled(), true);
    await pathInput.fill(`"${directory}"`);
    await select.click();
    await launcher.getByRole("button", { name: "Open project Existing local project" }).waitFor();

    const existing = await openProject(launcher);
    const existingFile = await existing.getByText(/^[a-f0-9]+\.warehouse\.sqlite3$/).innerText();
    const before = await readFile(join(directory, existingFile));
    const returned = await closeProject(existing);
    const returnedPath = returned.getByLabel("Project folder path");

    await returned.getByRole("button", { name: "Open project Existing local project" }).waitFor();
    await returnedPath.fill(join(directory, "missing"));
    await returned.getByRole("button", { name: "Use folder" }).click();
    await returned.getByRole("alert").filter({ hasText: "does not exist" }).waitFor();
    await returned.getByRole("button", { name: "New project" }).click();
    await returned.getByLabel("Project name").fill("Synthetic CSV project");
    await returned.getByRole("button", { name: "Create project" }).click();
    const created = await openProject(returned, "Synthetic CSV project");
    const createdFile = await created.getByText(/^[a-f0-9]+\.warehouse\.sqlite3$/).innerText();
    assert.equal((await stat(join(directory, createdFile))).isFile(), true);

    const imported = await openModule(created, "Import");
    const preparation = await openModule(created, "Data preparation");
    const results = await openModule(created, "Results");
    await imported.getByLabel("CSV file").setInputFiles(join(import.meta.dirname, "fixtures", "csv-valid.csv"));
    await imported.getByRole("table", { name: "Import preview" }).waitFor();
    await preparation.getByText("Import a CSV before preparing data.").waitFor();
    await imported.getByRole("button", { name: "Import CSV" }).click();
    await preparation.getByRole("button", { name: "Add step" }).click();
    await preparation.getByLabel("Operation").selectOption("filter");
    await preparation.getByLabel("Source column").selectOption({ label: "Kind" });
    await preparation.getByLabel("Match value").fill("Keep");
    await created.getByRole("button", { name: "Close project", exact: true }).click();
    await created.getByRole("button", { name: "Cancel", exact: true }).click();
    assert.equal(await preparation.getByLabel("Match value").inputValue(), "Keep");
    await preparation.getByRole("button", { name: "Apply", exact: true }).click();
    await results.getByRole("table", { name: "Saved result" }).getByRole("cell", { name: "0007", exact: true }).waitFor();
    const freshLauncher = await closeProject(created);
    assert.ok([imported, preparation, results].every(page => page.isClosed()));

    const reopened = await openProject(freshLauncher, "Synthetic CSV project");
    const reopenedResults = await openModule(reopened, "Results");
    const saved = reopenedResults.getByRole("table", { name: "Saved result" });
    await saved.getByRole("cell", { name: "0007", exact: true }).waitFor();
    assert.equal(await saved.locator("tbody tr").count(), 2);
    await saved.getByRole("button", { name: "Open original CSV line 4" }).click();
    const original = reopenedResults.getByRole("table", { name: "csv-valid.csv · CSV line 4" });
    await original.getByRole("cell", { name: "0042", exact: true }).waitFor();
    assert.equal(await original.locator("tbody tr").last().getByRole("cell").textContent(), "Two\nfixture lines");
    await reopenedResults.keyboard.press("Escape");
    await reopenedResults.getByRole("dialog", { name: "Original CSV record" }).waitFor({ state: "hidden" });
    assert.deepEqual(await readFile(join(directory, existingFile)), before);
  }));
