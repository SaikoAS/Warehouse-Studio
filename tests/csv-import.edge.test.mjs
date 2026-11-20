import assert from "node:assert/strict";
import test from "node:test";
import { withEdgeTestService } from "./edge-test-service.mjs";

test("Edge previews corrected CSV options and validates the full import", () =>
  withEdgeTestService([], async ({ openLauncher, openProject, openModule }) => {
    const project = await openProject(await openLauncher());
    const preparation = await openModule(project, "Data preparation");
    const page = await openModule(project, "Import");
    const file = page.getByLabel("CSV file");
    const submit = page.getByRole("button", { name: "Import CSV" });
    const preview = page.getByRole("table", { name: "Import preview" });
    await file.setInputFiles({
      name: "ambiguous.csv", mimeType: "text/csv", buffer: Buffer.from("0007;ä,1\r\n0042;Text,2\r\n"),
    });
    await page.getByRole("alert").filter({ hasText: "Choose a delimiter" }).waitFor();
    assert.equal(await submit.isDisabled(), true);
    await page.getByLabel("Delimiter", { exact: true }).selectOption(",");
    await page.getByLabel("Column names", { exact: true }).selectOption("custom");
    await page.getByLabel("Custom column names", { exact: true }).fill("Code,Quantity");
    await preview.getByRole("cell", { name: "0007;ä", exact: true }).waitFor();
    await page.getByLabel("Character encoding").selectOption("windows-1252");
    await preview.getByRole("cell", { name: "0007;Ã¤", exact: true }).waitFor();
    assert.equal(await preview.locator("tbody tr").first().getByRole("rowheader").innerText(), "1");
    await preparation.getByText("Import a CSV before preparing data.").waitFor();
    await project.getByRole("button", { name: "Close project", exact: true }).click();
    await project.getByRole("button", { name: "Cancel", exact: true }).click();
    await preview.getByRole("cell", { name: "0007;Ã¤", exact: true }).waitFor();
    await page.bringToFront();

    await file.setInputFiles({
      name: "late-error.csv", mimeType: "text/csv",
      buffer: Buffer.from("Article,Note\r\n" + "0007,complete\r\n".repeat(12) + '0042,"incomplete\r\nrecord'),
    });
    await page.getByLabel("Column names", { exact: true }).selectOption("file");
    await page.getByLabel("Character encoding").selectOption("utf-8");
    await preview.getByRole("columnheader", { name: "Article" }).waitFor();
    assert.equal(await preview.locator("tbody tr").count(), 10);
    await submit.click();
    await page.getByRole("alert").filter({ hasText: "Invalid CSV at line 14" }).waitFor();
    await file.setInputFiles({
      name: "corrected.csv", mimeType: "text/csv", buffer: Buffer.from('Article,Note\r\n0007,"Test\r\nline"\r\n'),
    });
    await preview.getByRole("cell", { name: "0007", exact: true }).waitFor();
    assert.equal(await page.getByRole("alert").count(), 0);
    const releaseImport = Promise.withResolvers();
    await page.route("**/api/csv-import", async route => {
      await releaseImport.promise;
      await route.continue();
    }, { times: 1 });
    try {
      const sent = page.waitForRequest("**/api/csv-import");
      await submit.click();
      await sent;
      await project.getByRole("button", { name: "Close project", exact: true }).click();
      await project.getByRole("alert").filter({ hasText: "A write is still running" }).waitFor();
    } finally {
      releaseImport.resolve();
    }
    await preparation.getByRole("table", { name: "Source", exact: true }).getByRole("cell", { name: "0007" }).waitFor();
  }));
