import { useState } from "react";

export async function request<T>(action: string, data: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch("/api/" + action, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal,
  });
  if (!response.headers.get("Content-Type")?.startsWith("application/json")) {
    throw new Error("The local service could not process the request.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The request failed.");
  return result;
}

export function actionError(cause: unknown) {
  return cause instanceof Error ? cause.message : "Could not reach the local service.";
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(actionError(cause));
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, run, setError };
}
