import assert from "node:assert/strict";
import test from "node:test";
import { withEdgeTestService } from "./edge-test-service.mjs";

test("Edge filters quoted Windows newlines and accepts 4,096 Unicode code points", () =>
  withEdgeTestService([], async ({ openLauncher, openProject, openModule }) => {
    const project = await openProject(await openLauncher());
    const page = await openModule(project, "Data preparation");
    const results = await openModule(project, "Results");
    const imported = await openModule(project, "Import");

    const longValue = "a".repeat(4095) + "📦";
    await imported.getByLabel("CSV file").setInputFiles({
      name: "synthetic-filter.csv", mimeType: "text/csv",
      buffer: Buffer.from(`Article;Note\r\n0007;"Alpha\r\nBeta"\r\n0011;${longValue}\r\n`),
    });
    await imported.getByRole("button", { name: "Import CSV" }).click();
    await page.getByRole("table", { name: "Source", exact: true }).waitFor();
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Operation").selectOption("filter");
    await page.getByLabel("Source column").selectOption({ label: "Note" });

    const input = page.getByLabel("Match value");
    const apply = page.getByRole("button", { name: "Apply", exact: true });
    const preview = page.getByRole("table", { name: "Step preview" });
    const result = results.getByRole("table", { name: "Saved result" });
    async function expectOnly(table, article) {
      await table.getByRole("cell", { name: article, exact: true }).waitFor();
      assert.equal(await table.locator("tbody tr").count(), 1);
    }

    await input.fill("Alpha\r\nBeta");
    assert.equal(await input.inputValue(), "Alpha\nBeta");
    await expectOnly(preview, "0007");
    await apply.click();
    await expectOnly(result, "0007");

    await page.getByLabel("Matching rows").selectOption("remove");
    await expectOnly(preview, "0011");
    await apply.click();
    await expectOnly(result, "0011");

    await page.getByLabel("Matching rows").selectOption("keep");
    await input.fill("");
    // Browser text insertion exercises the textarea's native input constraints.
    await page.keyboard.insertText(longValue);
    assert.equal(await input.inputValue(), longValue);
    await expectOnly(preview, "0011");
    await apply.click();
    await expectOnly(result, "0011");

    await page.bringToFront();
    await input.press("End");
    await input.press("x");
    assert.equal(await input.inputValue(), longValue + "x");
    await page.getByRole("alert").filter({ hasText: "enter a match value of up to" }).waitFor();
    assert.equal(await apply.isDisabled(), true);
    assert.equal(await input.getAttribute("aria-invalid"), "true");
    await expectOnly(result, "0011");
  }));
