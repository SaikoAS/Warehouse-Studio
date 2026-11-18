import { useEffect, useState, type FormEvent } from "react";
import { actionError, request, useAction } from "./local-service";

type CellType = "text" | "decimal";
type View = "source" | "preview" | "result";
type Step = { column: number } & (
  | { operation: "rename"; name: string }
  | { operation: "filter"; mode: "keep" | "remove"; value: string }
  | { operation: "convert"; target: CellType; locale: string }
);

interface Column {
  name: string;
  type: CellType;
}

interface Source {
  name: string;
  bytes: number;
  revision: number;
  columns: Column[];
  steps: Step[];
  hasResult: boolean;
}

interface SavedPreparation {
  maxBytes: number;
  maxCellLength: number;
  maxSteps: number;
  source: Source | null;
}

interface Page {
  columns: Column[];
  rows: [line: number, cells: string[]][];
  total: number;
  pageSize: number;
}

const operations = { rename: "Rename column", filter: "Filter rows", convert: "Convert type" } as const;
const viewLabels = { source: "Source", preview: "Step preview", result: "Saved result" } as const;

function exceedsCharacterLimit(value: string, limit: number) {
  let count = 0;
  for (const character of value) {
    count += 1;
    if (count > limit) return true;
  }
  return false;
}

function newStep(operation: Step["operation"], column: number): Step {
  switch (operation) {
    case "rename": return { operation, column, name: "" };
    case "filter": return { operation, column, mode: "keep", value: "" };
    case "convert": return { operation, column, target: "text", locale: "" };
  }
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read this file. Choose it again."));
    reader.onload = () => {
      const data = String(reader.result);
      resolve(data.slice(data.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

function ImportForm({ busy, maxBytes, onImport }: {
  busy: boolean;
  maxBytes: number;
  onImport: (file: File, headers: string | null) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [custom, setCustom] = useState(false);
  const [headers, setHeaders] = useState("");
  const tooLarge = file !== null && file.size > maxBytes;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (file && !tooLarge) onImport(file, custom ? headers : null);
  }

  return <form onSubmit={submit}>
    <label htmlFor="source-file">CSV file</label>
    <input id="source-file" type="file" accept=".csv,text/csv" required disabled={busy}
      aria-describedby="csv-format" onChange={event => setFile(event.target.files?.[0] ?? null)} />
    <small id="csv-format">UTF-8, semicolon-delimited, up to {maxBytes / (1024 * 1024)} MiB.</small>
    {tooLarge && <p role="alert">This file exceeds the CSV size limit.</p>}
    <label htmlFor="csv-header-mode">Column names</label>
    <select id="csv-header-mode" disabled={busy} value={custom ? "custom" : "file"}
      onChange={event => setCustom(event.target.value === "custom")}>
      <option value="file">Use the first CSV row</option>
      <option value="custom">Enter names for a CSV without headers</option>
    </select>
    {custom && <>
      <label htmlFor="csv-headers">Custom column names (separated by semicolons)</label>
      <input id="csv-headers" required maxLength={16_384} disabled={busy}
        value={headers} onChange={event => setHeaders(event.target.value)} />
    </>}
    <div className="actions"><button disabled={busy || !file || tooLarge}>Import CSV</button></div>
  </form>;
}

function StepFields({ step, columns, invalidFilter, onChange }: {
  step: Step;
  columns: Column[];
  invalidFilter: boolean;
  onChange: (step: Step) => void;
}) {
  return <>
    <label htmlFor="step-operation">Operation</label>
    <select id="step-operation" value={step.operation}
      onChange={event => onChange(newStep(event.target.value as Step["operation"], step.column))}>
      {Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select>
    <label htmlFor="step-column">Source column</label>
    <select id="step-column" value={step.column}
      onChange={event => onChange({ ...step, column: Number(event.target.value) })}>
      {columns.map((column, index) => <option key={column.name} value={index}>{column.name}</option>)}
    </select>
    {step.operation === "rename" && <>
      <label htmlFor="new-column-name">New column name</label>
      <input id="new-column-name" maxLength={120} value={step.name}
        onChange={event => onChange({ ...step, name: event.target.value })} />
    </>}
    {step.operation === "filter" && <>
      <label htmlFor="filter-mode">Matching rows</label>
      <select id="filter-mode" value={step.mode}
        onChange={event => onChange({ ...step, mode: event.target.value === "remove" ? "remove" : "keep" })}>
        <option value="keep">Keep exact matches</option>
        <option value="remove">Remove exact matches</option>
      </select>
      <label htmlFor="filter-value">Match value</label>
      <textarea id="filter-value" rows={2} value={step.value} aria-invalid={invalidFilter}
        aria-describedby={invalidFilter ? "invalid-filter" : undefined}
        onChange={event => onChange({ ...step, value: event.target.value })} />
    </>}
    {step.operation === "convert" && <>
      <label htmlFor="target-type">Target type</label>
      <select id="target-type" value={step.target}
        onChange={event => onChange({ ...step, target: event.target.value === "decimal" ? "decimal" : "text" })}>
        <option value="text">Text</option>
        <option value="decimal">Decimal</option>
      </select>
      {step.target === "decimal" && <>
        <label htmlFor="decimal-locale">Decimal locale</label>
        <select id="decimal-locale" value={step.locale}
          onChange={event => onChange({ ...step, locale: event.target.value })}>
          <option value="">Choose a locale</option>
          <option value="de-DE">German (Germany) — decimal comma</option>
          <option value="en-US">English (United States) — decimal point</option>
        </select>
      </>}
    </>}
  </>;
}

function DataTable({ projectKey, revision, view, steps, selected }: {
  projectKey: string;
  revision: number;
  view: View;
  steps?: Step[];
  selected?: number;
}) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ page: Page } | { error: string } | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [steps, selected]);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    const timer = window.setTimeout(async () => {
      try {
        const page = await request<Page>("csv-page", {
          key: projectKey, revision, view,
          steps: selected === undefined ? undefined : steps?.slice(0, selected + 1),
          through: selected, offset,
        }, controller.signal);
        if (!controller.signal.aborted) setData({ page });
      } catch (cause) {
        if (!controller.signal.aborted) setData({ error: actionError(cause) });
      }
    }, view === "preview" ? 180 : 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [projectKey, revision, view, steps, selected, offset]);

  if (data === null) return <p role="status">Loading {viewLabels[view].toLowerCase()}…</p>;
  if ("error" in data) return <p role="alert">{data.error}</p>;
  const { columns, rows, total, pageSize } = data.page;
  return <>
    <div className="table-scroll" tabIndex={0} role="region" aria-label={`${viewLabels[view]} table`}>
      <table>
        <caption>{viewLabels[view]}</caption>
        <thead><tr><th scope="col">CSV line</th>{columns.map(column => <th scope="col" key={column.name}>
          {column.name}<small>{column.type}</small>
        </th>)}</tr></thead>
        <tbody>{rows.map(([line, cells]) => <tr key={line}>
          <th scope="row">{line}</th>{cells.map((cell, index) => <td key={index}>{cell}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    <div className="row table-footer">
      <span role="status">{total === 0 ? "No data rows." : `${offset + 1}–${offset + rows.length} of ${total} rows`}</span>
      {total > pageSize && <div className="actions">
        <button type="button" className="secondary" disabled={offset === 0}
          onClick={() => setOffset(offset - pageSize)}>Previous rows</button>
        <button type="button" className="secondary" disabled={offset + pageSize >= total}
          onClick={() => setOffset(offset + pageSize)}>Next rows</button>
      </div>}
    </div>
  </>;
}

export function CsvPreparation({ projectKey }: { projectKey: string }) {
  const [saved, setSaved] = useState<SavedPreparation | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [view, setView] = useState<View>("source");
  const [notice, setNotice] = useState("");
  const { busy, error, run } = useAction();
  const source = saved?.source;
  const currentStep = selected === null ? null : steps[selected];
  const invalidFilter = saved ? steps.findIndex(step =>
    step.operation === "filter" && exceedsCharacterLimit(step.value, saved.maxCellLength)) : -1;
  const previewBlocked = view === "preview" && selected !== null && invalidFilter >= 0 && invalidFilter <= selected;

  function show(persisted: SavedPreparation) {
    setSaved(persisted);
    setSteps(persisted.source?.steps ?? []);
    setSelected(null);
    setView(persisted.source?.hasResult ? "result" : "source");
  }

  function reload() {
    setNotice("");
    void run(async () => show(await request<SavedPreparation>("preparation", { key: projectKey })));
  }

  useEffect(reload, [projectKey]);

  function importCsv(file: File, headers: string | null) {
    setNotice("");
    void run(async () => show(await request<SavedPreparation>("csv-import", {
      key: projectKey, name: file.name, content: await readFile(file), headers,
    })));
  }

  function apply() {
    if (!source) return;
    setNotice("");
    void run(async () => {
      setSaved(await request<SavedPreparation>("csv-apply", { key: projectKey, revision: source.revision, steps }));
      setView("result");
      setNotice("Result saved.");
    });
  }

  function select(index: number) {
    setSelected(index);
    setView("preview");
    setNotice("");
  }

  function move(index: number, destination: number) {
    const ordered = [...steps];
    [ordered[index], ordered[destination]] = [ordered[destination], ordered[index]];
    setSteps(ordered);
    select(destination);
  }

  function remove(index: number) {
    const remaining = steps.filter((_, position) => index !== position);
    setSteps(remaining);
    if (remaining.length) select(Math.min(index, remaining.length - 1));
    else {
      setSelected(null);
      setView("source");
      setNotice("");
    }
  }

  return <section aria-labelledby="preparation-heading">
    <div className="row">
      <h2 id="preparation-heading">CSV preparation</h2>
      {(source || error) && <button type="button" className="secondary" disabled={busy}
        onClick={reload}>Reload saved preparation</button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!saved && busy && <p role="status">Loading preparation…</p>}
    {saved && !source && <ImportForm busy={busy} maxBytes={saved.maxBytes} onImport={importCsv} />}
    {saved && source && <>
      <p className="path">{source.name} · {source.bytes.toLocaleString()} bytes</p>
      <fieldset className="preparation-editor" disabled={busy}>
        <legend>Preparation steps</legend>
        {steps.length > 0 && <ol className="step-list">
          {steps.map((step, index) => <li key={index}>
            <button type="button" className="secondary" aria-pressed={selected === index}
              onClick={() => select(index)}>{index + 1}. {operations[step.operation]} · {source.columns[step.column].name}</button>
          </li>)}
        </ol>}
        <div className="actions">
          <button type="button" className="secondary" disabled={steps.length >= saved.maxSteps} onClick={() => {
            setSteps([...steps, newStep("rename", 0)]);
            select(steps.length);
          }}>Add step</button>
          <button type="button" disabled={invalidFilter >= 0} onClick={apply}>Apply</button>
        </div>
        {selected !== null && currentStep && <div className="step-fields">
          <StepFields step={currentStep} columns={source.columns} invalidFilter={invalidFilter === selected} onChange={step => {
            setSteps(steps.map((previous, index) => index === selected ? step : previous));
            select(selected);
          }} />
          <div className="actions">
            <button type="button" className="secondary" disabled={selected === 0}
              onClick={() => move(selected, selected - 1)}>Move up</button>
            <button type="button" className="secondary" disabled={selected === steps.length - 1}
              onClick={() => move(selected, selected + 1)}>Move down</button>
            <button type="button" className="secondary" onClick={() => remove(selected)}>Remove step</button>
          </div>
        </div>}
        {invalidFilter >= 0 && <p id="invalid-filter" role="alert">
          Step {invalidFilter + 1}: enter a match value of up to {saved.maxCellLength.toLocaleString()} characters.
        </p>}
      </fieldset>
      <div className="actions table-views" aria-label="Data view" role="group">
        {(Object.keys(viewLabels) as View[]).map(option => <button key={option} type="button" className="secondary"
          aria-pressed={view === option} disabled={(option === "preview" && selected === null) || (option === "result" && !source.hasResult)}
          onClick={() => setView(option)}>{viewLabels[option]}</button>)}
      </div>
      {!previewBlocked && <DataTable key={`${view}:${source.revision}`} projectKey={projectKey} revision={source.revision} view={view}
        steps={view === "preview" ? steps : undefined} selected={view === "preview" ? selected ?? undefined : undefined} />}
    </>}
  </section>;
}
