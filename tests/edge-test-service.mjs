import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { chromium } from "playwright-core";

export async function withEdgeTestService(args, exercise) {
  const directory = await mkdtemp(join(tmpdir(), "warehouse edge "));
  const service = spawn("python", ["-I", join(import.meta.dirname, "edge_fixture_server.py"), directory, ...args], {
    stdio: ["ignore", "pipe", "inherit"], windowsHide: true,
  });
  const stopped = new Promise(resolve => service.once("close", resolve));
  const stdout = createInterface({ input: service.stdout });
  const nextUrl = async () => {
    const [url] = await once(stdout, "line", { signal: AbortSignal.timeout(10_000) });
    return url;
  };
  let browser;
  try {
    const url = await Promise.race([
      nextUrl(),
      once(service, "exit").then(([code]) => { throw new Error(`Fixture server exited with ${code}.`); }),
    ]);
    browser = await chromium.launch({ channel: "msedge", headless: true });
    console.log(`Microsoft Edge ${browser.version()}`);
    const context = await browser.newContext();
    context.setDefaultTimeout(8_000);
    const origin = new URL(url).origin;
    await context.route("**/*", route =>
      new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await exercise({ directory, url, nextUrl, context });
  } finally {
    await browser?.close();
    stdout.close();
    service.kill();
    await stopped;
    await rm(directory, { recursive: true, force: true, maxRetries: 3 });
  }
}
