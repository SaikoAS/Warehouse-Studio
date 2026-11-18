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
  withEdgeTestService(["--launcher"], async ({ directory, url, nextUrl, context }) => {
    const launcher = await context.newPage();
    await launcher.goto(url);
    const pathInput = launcher.getByLabel("Project folder path");
    const select = launcher.getByRole("button", { name: "Use folder" });
    const browse = launcher.getByRole("button", { name: "Browse (optional)" });

    await browse.click();
    await launcher.getByRole("alert").filter({ hasText: "Paste a local path" }).waitFor();
    assert.equal(await pathInput.isEnabled(), true);
    await pathInput.fill(`"${directory}"`);
    await select.click();
    await launcher.getByRole("button", { name: "Open project Existing local project" }).waitFor();

    async function openProject(name) {
      const destination = nextUrl();
      await launcher.getByRole("button", { name: `Open project ${name}` }).click();
      const projectUrl = await destination;
      assert.ok(projectUrl.startsWith(`${url}#project=`));
      const project = await context.newPage();
      await project.goto(projectUrl);
      await project.getByRole("heading", { name, exact: true }).waitFor();
      return project;
    }

    const existing = await openProject("Existing local project");
    const existingFile = await existing.getByText(/^[a-f0-9]+\.warehouse\.sqlite3$/).innerText();
    const before = await readFile(join(directory, existingFile));

    await pathInput.fill(join(directory, "missing"));
    await select.click();
    await launcher.getByRole("alert").filter({ hasText: "does not exist" }).waitFor();
    await launcher.getByRole("button", { name: "New project" }).click();
    await launcher.getByLabel("Project name").fill("Synthetic CSV project");
    await launcher.getByRole("button", { name: "Create project" }).click();
    const created = await openProject("Synthetic CSV project");
    const createdFile = await created.getByText(/^[a-f0-9]+\.warehouse\.sqlite3$/).innerText();
    assert.equal((await stat(join(directory, createdFile))).isFile(), true);

    await created.getByLabel("CSV file").setInputFiles(join(import.meta.dirname, "fixtures", "csv-valid.csv"));
    await created.getByRole("button", { name: "Import CSV" }).click();
    await created.getByRole("button", { name: "Add step" }).click();
    await created.getByLabel("Operation").selectOption("filter");
    await created.getByLabel("Source column").selectOption({ label: "Kind" });
    await created.getByLabel("Match value").fill("Keep");
    await created.getByRole("button", { name: "Apply", exact: true }).click();
    await created.getByRole("table", { name: "Saved result" }).getByRole("cell", { name: "0007", exact: true }).waitFor();
    await created.close();

    const reopened = await openProject("Synthetic CSV project");
    const saved = reopened.getByRole("table", { name: "Saved result" });
    await saved.getByRole("cell", { name: "0007", exact: true }).waitFor();
    assert.equal(await saved.locator("tbody tr").count(), 2);
    await existing.getByLabel("CSV file").waitFor();
    assert.deepEqual(await readFile(join(directory, existingFile)), before);
  }));
