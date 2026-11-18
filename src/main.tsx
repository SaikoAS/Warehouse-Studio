import { useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { CsvPreparation } from "./csv-preparation";
import { request, useAction } from "./local-service";
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
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const { busy, error, run } = useAction();

  function showFolder(picked: Folder) {
    setFolder(picked);
    setFolderPath(picked.path);
    setCreating(false);
    setName("");
  }

  function selectFolder(event: FormEvent) {
    event.preventDefault();
    void run(async () => showFolder(await request<Folder>("select-folder", { path: folderPath })));
  }

  function browse() {
    void run(async () => {
      const picked = await request<Folder | null>("choose-folder");
      if (picked) showFolder(picked);
    });
  }

  function create(event: FormEvent) {
    event.preventDefault();
    if (!folder) return;
    void run(async () => {
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
          aria-describedby="folder-path-hint" onChange={event => setFolderPath(event.target.value)} />
        <small id="folder-path-hint">Paste an absolute local path from File Explorer.</small>
        <div className="actions">
          <button disabled={busy || !folderPath.trim()}>Use folder</button>
          <button type="button" className="secondary" disabled={busy} onClick={browse}>Browse (optional)</button>
        </div>
      </form>
    </section>
    {folder && <section aria-labelledby="projects-heading">
      <div className="row">
        <div><h2 id="projects-heading">Projects in this folder</h2>
          <p className="path">{folder.path}</p>
        </div>
        <div className="actions">
          <button className="secondary" disabled={busy} onClick={() => void run(async () =>
            setFolder(await request<Folder>("list", { key: folder.folder })))}>Refresh</button>
          <button disabled={busy || creating} onClick={() => setCreating(true)}>New project</button>
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
          onClick={() => void run(async () => { await request("open", { key: item.key }); })}>Open project</button>
      </li>)}</ul>
      {folder.warnings.map(warning => <p role="alert" key={warning}>{warning}</p>)}
    </section>}
  </main>;
}

function ProjectWindow({ projectKey }: { projectKey: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");
  const { busy, error, run } = useAction();

  function show(saved: Project) {
    setProject(saved);
    setName(saved.name);
    document.title = saved.name + " · Warehouse Studio";
  }

  function reload() {
    setNotice("");
    void run(async () => show(await request<Project>("project", { key: projectKey })));
  }
  useEffect(reload, [projectKey]);

  function save(event: FormEvent) {
    event.preventDefault();
    if (!project) return;
    setNotice("");
    void run(async () => {
      show(await request<Project>("save", { key: projectKey, revision: project.revision, name }));
      setNotice("Project saved.");
    });
  }

  return <main>
    <h1>{project?.name ?? "Project"}</h1>
    {error && <p role="alert">{error}</p>}
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
    {project && <CsvPreparation key={projectKey} projectKey={projectKey} />}
  </main>;
}

function App() {
  const key = new URLSearchParams(window.location.hash.slice(1)).get("project");
  return <>
    <header><div className="brand"><span className="mark" aria-hidden="true">W</span>Warehouse Studio</div></header>
    {key === null ? <Launcher /> : <ProjectWindow projectKey={key} />}
  </>;
}

createRoot(document.getElementById("root")!).render(<App />);
