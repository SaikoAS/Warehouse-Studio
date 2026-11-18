import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import test from "node:test";
import { chromium } from "playwright-core";

test("Edge filters quoted Windows newlines and accepts 4,096 Unicode code points", async () => {
  const directory = await mkdtemp(join(tmpdir(), "warehouse-edge-"));
  const service = spawn("python", [join(import.meta.dirname, "edge_fixture_server.py"), directory], {
    stdio: ["ignore", "pipe", "inherit"], windowsHide: true,
  });
  const stopped = new Promise(resolve => service.once("close", resolve));
  const stdout = createInterface({ input: service.stdout });
  let browser;
  try {
    const [url] = await Promise.race([
      once(stdout, "line", { signal: AbortSignal.timeout(10_000) }),
      once(service, "exit").then(([code]) => { throw new Error(`Fixture server exited with ${code}.`); }),
    ]);
    browser = await chromium.launch({ channel: "msedge" });
    console.log(`Microsoft Edge ${browser.version()}`);
    const page = await browser.newPage();
    page.setDefaultTimeout(8_000);
    const origin = new URL(url).origin;
    await page.route("**/*", route =>
      new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await page.goto(url);

    const longValue = "a".repeat(4095) + "📦";
    await page.getByLabel("CSV file").setInputFiles({
      name: "synthetic-filter.csv", mimeType: "text/csv",
      buffer: Buffer.from(`Article;Note\r\n0007;"Alpha\r\nBeta"\r\n0011;${longValue}\r\n`),
    });
    await page.getByRole("button", { name: "Import CSV" }).click();
    await page.getByRole("table", { name: "Source", exact: true }).waitFor();
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Operation").selectOption("filter");
    await page.getByLabel("Source column").selectOption({ label: "Note" });

    const input = page.getByLabel("Match value");
    const apply = page.getByRole("button", { name: "Apply", exact: true });
    const preview = page.getByRole("table", { name: "Step preview" });
    const result = page.getByRole("table", { name: "Saved result" });
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

    await input.focus();
    await input.press("End");
    await page.keyboard.insertText("x");
    await page.getByRole("alert").filter({ hasText: "enter a match value of up to" }).waitFor();
    assert.equal(await apply.isDisabled(), true);
    assert.equal(await input.getAttribute("aria-invalid"), "true");
    await page.getByRole("button", { name: "Saved result", exact: true }).click();
    await expectOnly(result, "0011");
  } finally {
    await browser?.close();
    stdout.close();
    service.kill();
    await stopped;
    await rm(directory, { recursive: true, force: true, maxRetries: 3 });
  }
});
