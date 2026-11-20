import { useLayoutEffect } from "react";
import { projectSession } from "./local-service";

export const modules = {
  import: "Import",
  preparation: "Data preparation",
  results: "Results",
};

export type Module = keyof typeof modules;
type Change = "project-renamed" | "source-imported" | "result-applied";
type Work = { dirty: boolean; writing: boolean };

declare global {
  interface Window {
    warehouseWork?: () => Work;
    closeWarehouseModule?: () => void;
  }
}

const updates = projectSession ? new BroadcastChannel("warehouse:" + projectSession) : null;
let closing = false;

export function publishChange(change: Change) {
  updates?.postMessage(change);
}

export function useProjectUpdates(handle: (change: Change) => void) {
  useLayoutEffect(() => {
    const listener = (event: MessageEvent<Change>) => handle(event.data);
    updates?.addEventListener("message", listener);
    return () => updates?.removeEventListener("message", listener);
  }, [handle]);
}

export function useCloseProtection(work: () => Work) {
  useLayoutEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (closing) return;
      const { dirty, writing } = work();
      if (dirty || writing) {
        event.preventDefault();
        event.returnValue = true;
      }
    };
    window.warehouseWork = work;
    window.addEventListener("beforeunload", guard);
    return () => {
      delete window.warehouseWork;
      window.removeEventListener("beforeunload", guard);
    };
  }, [work]);
}

export function closeWithProject() {
  closing = true;
  window.close();
}

export function useModuleLifetime() {
  useLayoutEffect(() => {
    window.closeWarehouseModule = closeWithProject;
    const check = () => {
      if (window.opener?.closed) closeWithProject();
    };
    // Also covers a native close if the project page's shutdown callback is skipped.
    const timer = window.setInterval(check, 500);
    check();
    return () => {
      window.clearInterval(timer);
      delete window.closeWarehouseModule;
    };
  }, []);
}
