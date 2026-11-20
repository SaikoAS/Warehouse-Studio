import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { CsvPreparation } from "./csv-preparation";
import { actionError, request, useAction } from "./local-service";
import { closeWithProject, modules, publishChange, useCloseProtection, useModuleLifetime,
  useProjectUpdates, type Module } from "./project-windows";
import "./studio.css";

interface ProjectEntry {
  key: string;
  name: string;
  file: string;
}
interface Folder {
  folder: string;
  path: string;
  projects: ProjectEntry[];
  warnings: string[];
}
interface Project {
  name: string;
  revision: number;
  file: string;
}

function Launcher() {
  const [folder, setFolder] = useState<Folder | null>(null);
  const [folderPath, setFolderPath] = useState("");
  const [browsing, setBrowsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const { busy, error, run, setError } = useAction();
  const acceptPickerResult = useRef(false);

  useEffect(() => {
    const key = new URLSearchParams(window.location.search).get("folder");
    if (key) runLauncherAction(async () => showFolder(await request<Folder>("list", { key })));
  }, []);

  function showFolder(picked: Folder) {
    setFolder(picked);
    setFolderPath(picked.path);
    setCreating(false);
    setName("");
  }

  function runLauncherAction(action: () => Promise<void>) {
    acceptPickerResult.current = false;
    void run(action);
  }

  function selectFolder(event: FormEvent) {
    event.preventDefault();
    runLauncherAction(async () => showFolder(await request<Folder>("select-folder", { path: folderPath })));
  }

  async function browse() {
    acceptPickerResult.current = true;
    setBrowsing(true);
    setError("");
    try {
      const picked = await request<Folder | null>("choose-folder");
      if (acceptPickerResult.current && picked) showFolder(picked);
    } catch (cause) {
      if (acceptPickerResult.current) setError(actionError(cause));
    } finally {
      setBrowsing(false);
    }
  }

  function create(event: FormEvent) {
    event.preventDefault();
    if (!folder) return;
    runLauncherAction(async () => {
      setFolder(await request<Folder>("create", { key: folder.folder, name }));
      setCreating(false);
      setName("");
    });
  }

  return <main>
    <h1>Projects</h1>
    {error && <p role="alert">{error}</p>}
    <section aria-labelledby="folder-heading">
      <h2 id="folder-heading">Data folder</h2>
      <form onSubmit={selectFolder}>
        <label htmlFor="folder-path">Project folder path</label>
        <input id="folder-path" required disabled={busy} value={folderPath} spellCheck={false}
          aria-describedby="folder-path-hint" onChange={event => {
            acceptPickerResult.current = false;
            setFolderPath(event.target.value);
          }} />
        <small id="folder-path-hint">Paste an absolute local path from File Explorer.</small>
        <div className="actions">
          <button disabled={busy || !folderPath.trim()}>Use folder</button>
          <button type="button" className="secondary" disabled={busy || browsing} onClick={browse}>
            {browsing ? "Waiting for folder picker…" : "Browse (optional)"}
          </button>
        </div>
      </form>
    </section>
    {folder && <section aria-labelledby="projects-heading">
      <div className="row">
        <div><h2 id="projects-heading">Projects in this folder</h2>
          <p className="path">{folder.path}</p>
        </div>
        <div className="actions">
          <button className="secondary" disabled={busy} onClick={() => runLauncherAction(async () =>
            setFolder(await request<Folder>("list", { key: folder.folder })))}>Refresh</button>
          <button disabled={busy || creating} onClick={() => {
            acceptPickerResult.current = false;
            setCreating(true);
          }}>New project</button>
        </div>
      </div>
      {creating && <form onSubmit={create}>
        <label htmlFor="new-name">Project name</label>
        <input id="new-name" autoFocus required maxLength={120} value={name} onChange={e => setName(e.target.value)} />
        <div className="actions">
          <button disabled={busy || !name.trim()}>Create project</button>
          <button className="secondary" type="button" disabled={busy} onClick={() => {setCreating(false); setName("");}}>Cancel</button>
        </div>
      </form>}
      {folder.projects.length === 0 && <p>No projects in this folder.</p>}
      <ul>{folder.projects.map(item => <li key={item.key} className="row">
        <div><strong>{item.name}</strong><small>{item.file}</small></div>
        <button className="secondary" aria-label={`Open project ${item.name}`} disabled={busy}
          onClick={() => runLauncherAction(async () => {
            await request("open", { key: item.key, folder: folder.folder });
            window.close();
          })}>Open project</button>
      </li>)}</ul>
      {folder.warnings.map(warning => <p role="alert" key={warning}>{warning}</p>)}
    </section>}
  </main>;
}

function ProjectWindow({ projectKey }: { projectKey: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmClose, setConfirmClose] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [closing, setClosing] = useState(false);
  const { busy, error, run, setError } = useAction();
  const windows = useRef(new Map<Module, Window>());
  const projectDirty = project !== null && name !== project.name;

  function pendingWork() {
    const dirty = projectDirty ? ["Project name"] : [];
    let writing = saving;
    for (const [module, child] of windows.current) {
      if (child.closed) continue;
      const state = child.warehouseWork?.();
      if (state?.dirty) dirty.push(modules[module]);
      writing ||= state?.writing ?? false;
    }
    return { dirty, writing };
  }

  useCloseProtection(() => {
    const work = pendingWork();
    return { dirty: work.dirty.length > 0, writing: work.writing };
  });

  function closeModules() {
    for (const child of windows.current.values()) {
      if (child.closed) continue;
      if (child.closeWarehouseModule) child.closeWarehouseModule();
      else child.close();
    }
  }

  useLayoutEffect(() => {
    window.addEventListener("pagehide", closeModules);
    return () => window.removeEventListener("pagehide", closeModules);
  }, []);

  function openModule(module: Module) {
    const existing = windows.current.get(module);
    if (existing && !existing.closed) {
      existing.focus();
      return;
    }
    const child = window.open("/modules/" + module + window.location.hash, module, "popup,width=1060,height=760");
    if (child) windows.current.set(module, child);
    else setError("Edge blocked the module window. Allow pop-ups for Warehouse Studio and try again.");
  }

  async function closeProject(discard = false) {
    const work = pendingWork();
    if (work.writing) {
      setError("A write is still running. Wait for it to finish, then close the project.");
      return;
    }
    if (work.dirty.length && !discard) {
      setConfirmClose(work.dirty);
      return;
    }
    setClosing(true);
    await run(async () => {
      await request("session-close", { key: projectKey });
      closeModules();
      closeWithProject();
    });
    setClosing(false);
  }

  function show(saved: Project) {
    setProject(saved);
    setName(saved.name);
    document.title = saved.name + " · Warehouse Studio";
  }

  function reload() {
    setNotice("");
    void run(async () => show(await request<Project>("project", { key: projectKey })));
  }
  useEffect(() => {
    void run(async () => {
      show(await request<Project>("project", { key: projectKey }));
      await request("session-ready", { key: projectKey });
    });
  }, [projectKey]);

  function save(event: FormEvent) {
    event.preventDefault();
    if (!project) return;
    setNotice("");
    setSaving(true);
    void run(async () => {
      show(await request<Project>("save", { key: projectKey, revision: project.revision, name }));
      publishChange("project-renamed");
      setNotice("Project saved.");
    }).finally(() => setSaving(false));
  }

  return <main>
    <h1>{project?.name ?? "Project"}</h1>
    {error && <p role="alert">{error}</p>}
    {project && <section aria-label="Project navigation">
      <div className="actions">
        {Object.entries(modules).map(([id, label]) =>
          <button key={id} type="button" disabled={closing || confirmClose.length > 0}
            onClick={() => openModule(id as Module)}>{label}</button>)}
        <button type="button" className="secondary" disabled={closing || confirmClose.length > 0}
          onClick={() => void closeProject()}>Close project</button>
      </div>
      {confirmClose.length > 0 && <fieldset>
        <legend>Unsaved changes</legend>
        <p>{confirmClose.join(", ")}</p>
        <div className="actions">
          <button type="button" className="secondary" autoFocus disabled={closing}
            onClick={() => setConfirmClose([])}>Cancel</button>
          <button type="button" disabled={closing}
            onClick={() => void closeProject(true)}>Discard changes and close</button>
        </div>
      </fieldset>}
    </section>}
    <section>
      <h2>Project details</h2>
      {project && <>
        <p className="path">{project.file}</p>
        <form onSubmit={save}>
          <label htmlFor="project-name">Project name</label>
          <input id="project-name" maxLength={120} required disabled={busy} value={name}
            onChange={e => { setName(e.target.value); setNotice(""); }} />
          <div className="actions">
            <button disabled={busy || !name.trim() || name.trim() === project.name}>Save changes</button>
          </div>
        </form>
      </>}
      {error && <button className="secondary" disabled={busy} onClick={reload}>Reload saved name</button>}
      {notice && <p role="status">{notice}</p>}
    </section>
  </main>;
}

function ModuleWindow({ projectKey, module }: { projectKey: string; module: Module }) {
  const [name, setName] = useState("");
  const { error, run } = useAction();
  useModuleLifetime();
  function loadProject() {
    void run(async () => {
      const project = await request<Project>("project", { key: projectKey });
      setName(project.name);
      document.title = project.name + " · " + modules[module] + " · Warehouse Studio";
    });
  }
  useEffect(loadProject, [projectKey, module]);
  useProjectUpdates(change => {
    if (change === "project-renamed") loadProject();
  });
  return <main>
    <h1>{modules[module]}</h1>
    {name && <p className="path">{name}</p>}
    {error && <p role="alert">{error}</p>}
    {name && <CsvPreparation key={projectKey} projectKey={projectKey} module={module} />}
  </main>;
}

function App() {
  const key = new URLSearchParams(window.location.hash.slice(1)).get("project");
  const path = window.location.pathname;
  const module = path.slice("/modules/".length);
  return <>
    <header><div className="brand"><span className="mark" aria-hidden="true">W</span>Warehouse Studio</div></header>
    {path === "/" || path === "/launcher" ? <Launcher /> :
      key === null ? <main><p role="alert">Open the project from the launcher.</p></main> :
      path.startsWith("/modules/") && Object.hasOwn(modules, module) ?
        <ModuleWindow module={module as Module} projectKey={key} /> :
        <ProjectWindow projectKey={key} />}
  </>;
}

createRoot(document.getElementById("root")!).render(<App />);
