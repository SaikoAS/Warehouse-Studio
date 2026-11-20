import { useEffect, useState, type FormEvent } from "react";
import { actionError, request, useAction } from "./local-service";

const encodings = { "utf-8": "UTF-8", "utf-16-le": "UTF-16 LE", "utf-16-be": "UTF-16 BE", "windows-1252": "Windows-1252" } as const;
const delimiters = { ";": "Semicolon ( ; )", ",": "Comma ( , )" } as const;

export interface CsvImportOptions {
  encoding: keyof typeof encodings;
  delimiter: keyof typeof delimiters;
  headers: string | null;
}

interface Draft {
  file: File | null;
  encoding: CsvImportOptions["encoding"] | null;
  delimiter: CsvImportOptions["delimiter"] | null;
  hasHeader: boolean;
  headers: string;
}

interface Preview {
  suggestedEncoding: Draft["encoding"];
  suggestedDelimiter: Draft["delimiter"];
  sample: {
    name: string;
    encoding: CsvImportOptions["encoding"];
    delimiter: CsvImportOptions["delimiter"];
    columns: { name: string }[];
    rows: [line: number, cells: string[]][];
  } | null;
  error: string | null;
}

export function readFile(file: Blob): Promise<string> {
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

export function CsvImport({ projectKey, disabled, maxBytes, maxPreviewBytes, onImport, onReload, onDirtyChange }: {
  projectKey: string;
  disabled: boolean;
  maxBytes: number;
  maxPreviewBytes: number;
  onImport: (file: File, options: CsvImportOptions) => Promise<void>;
  onReload: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState<Draft>({ file: null, encoding: null, delimiter: null, hasHeader: true, headers: "" });
  const [response, setResponse] = useState<{ draft: Draft; preview: Preview } | null>(null);
  const { busy, error, run, setError } = useAction();
  const { file, encoding, delimiter, hasHeader, headers } = draft;
  const customHeaders = hasHeader ? null : headers;
  const tooLarge = file !== null && file.size > maxBytes;
  const preview = response?.draft === draft ? response.preview : null;
  const sample = preview?.sample;

  useEffect(() => {
    onDirtyChange(file !== null || !hasHeader || encoding !== null || delimiter !== null);
  }, [file, hasHeader, encoding, delimiter, onDirtyChange]);

  useEffect(() => {
    if (file === null || tooLarge) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      let result: Preview;
      try {
        const content = await readFile(file.slice(0, maxPreviewBytes));
        result = await request<Preview>("csv-preview", {
          key: projectKey, name: file.name, content, encoding, delimiter, headers: customHeaders,
          truncated: file.size > maxPreviewBytes,
        }, controller.signal);
      } catch (cause) {
        result = { suggestedEncoding: null, suggestedDelimiter: null, sample: null, error: actionError(cause) };
      }
      if (!controller.signal.aborted) setResponse({ draft, preview: result });
    }, 150);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [draft, file, encoding, delimiter, customHeaders, tooLarge, maxPreviewBytes, projectKey]);

  function changeDraft(changes: Partial<Draft>) {
    setError("");
    setDraft(previous => ({ ...previous, ...changes }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (file && sample && !busy && !disabled) {
      void run(() => onImport(file, { encoding: sample.encoding, delimiter: sample.delimiter, headers: customHeaders }));
    }
  }

  return <form onSubmit={submit}>
    <fieldset className="csv-import-fields" disabled={disabled || busy} aria-label="CSV options">
      <label htmlFor="source-file">CSV file</label>
      <input id="source-file" type="file" accept=".csv,text/csv" required
        aria-describedby="csv-format" onChange={event => changeDraft({ file: event.target.files?.[0] ?? null })} />
      <small id="csv-format">Up to {maxBytes / (1024 * 1024)} MiB.</small>
      {tooLarge && <p role="alert">This file exceeds the CSV size limit.</p>}
      <label htmlFor="csv-encoding">Character encoding</label>
      <select id="csv-encoding" value={encoding ?? ""} aria-describedby="csv-encoding-hint"
        onChange={event => changeDraft({ encoding: (event.target.value || null) as Draft["encoding"] })}>
        <option value="">Detect automatically</option>
        {Object.entries(encodings).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
      </select>
      <small id="csv-encoding-hint">{preview?.suggestedEncoding && `Suggested: ${encodings[preview.suggestedEncoding]}`}</small>
      <label htmlFor="csv-delimiter">Delimiter</label>
      <select id="csv-delimiter" value={delimiter ?? ""} aria-describedby="csv-delimiter-hint"
        onChange={event => changeDraft({ delimiter: (event.target.value || null) as Draft["delimiter"] })}>
        <option value="">Detect automatically</option>
        {Object.entries(delimiters).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
      </select>
      <small id="csv-delimiter-hint">{preview?.suggestedDelimiter && `Suggested: ${delimiters[preview.suggestedDelimiter]}`}</small>
      <label htmlFor="csv-header-mode">Column names</label>
      <select id="csv-header-mode" value={hasHeader ? "file" : "custom"}
        onChange={event => changeDraft({ hasHeader: event.target.value === "file" })}>
        <option value="file">Use the first CSV row</option>
        <option value="custom">Enter names for a CSV without headers</option>
      </select>
      {!hasHeader && <>
        <label htmlFor="csv-headers">Custom column names</label>
        <input id="csv-headers" required maxLength={16_384} value={headers}
          aria-describedby="csv-headers-hint" onChange={event => changeDraft({ headers: event.target.value })} />
        <small id="csv-headers-hint">Separate the names using the chosen delimiter.</small>
      </>}
    </fieldset>
    {file && !tooLarge && !preview && <p role="status">Loading import preview…</p>}
    {preview?.error && <p role="alert">{preview.error}</p>}
    {sample && <>
      <p>{sample.name} · {encodings[sample.encoding]} · {delimiters[sample.delimiter]}</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Import preview table">
        <table>
          <caption>Import preview</caption>
          <thead><tr><th scope="col">CSV line</th>{sample.columns.map(column =>
            <th scope="col" key={column.name}>{column.name}</th>)}</tr></thead>
          <tbody>{sample.rows.map(([line, cells]) => <tr key={line}>
            <th scope="row">{line}</th>{cells.map((cell, index) => <td key={index}>{cell}</td>)}
          </tr>)}</tbody>
        </table>
      </div>
      <small>The full file is validated when you select Import CSV.</small>
    </>}
    {busy && <p role="status">Validating and importing CSV…</p>}
    {error && <p role="alert">{error}</p>}
    <div className="actions">
      <button disabled={disabled || busy || !sample}>Import CSV</button>
      {error && <button type="button" className="secondary" disabled={disabled || busy}
        onClick={() => { setError(""); onReload(); }}>Reload saved preparation</button>}
    </div>
  </form>;
}
