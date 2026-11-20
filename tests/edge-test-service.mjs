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
    const host = await context.newPage();
    await host.goto(url);
    async function openApp(destination) {
      const opened = host.waitForEvent("popup");
      await host.evaluate(next => { window.open(next, "_blank", "popup"); }, destination);
      return opened;
    }
    async function openProject(launcher, name = "Existing local project") {
      const destination = nextUrl();
      const closed = launcher.waitForEvent("close");
      await launcher.getByRole("button", { name: `Open project ${name}` }).click();
      const project = await openApp(await destination);
      await project.getByRole("heading", { name, exact: true }).waitFor();
      await closed;
      return project;
    }
    async function openLauncher() {
      const launcher = await openApp(url);
      await launcher.getByLabel("Project folder path").fill(directory);
      await launcher.getByRole("button", { name: "Use folder" }).click();
      return launcher;
    }
    async function openModule(project, name) {
      const popup = project.waitForEvent("popup");
      await project.getByRole("button", { name, exact: true }).click();
      const module = await popup;
      await module.getByRole("heading", { name, exact: true }).waitFor();
      return module;
    }
    async function closeProject(project) {
      const closed = project.waitForEvent("close");
      const destination = nextUrl();
      await project.getByRole("button", { name: "Close project", exact: true }).click();
      await closed;
      const ended = await context.request.post(new URL("/api/fixture-project-ended", url).href, {
        data: {}, headers: { Origin: origin },
      });
      if (!ended.ok()) throw new Error("Failed to signal the fake Edge process exit.");
      return openApp(await destination);
    }
    await exercise({ directory, url, context, openApp, openProject, openLauncher, openModule, closeProject });
  } finally {
    await browser?.close();
    stdout.close();
    service.kill();
    await stopped;
    await rm(directory, { recursive: true, force: true, maxRetries: 3 });
  }
}
