import { createRoot } from "react-dom/client";
import "./studio.css";

function App() {
  return (
    <>
      <header><div className="brand"><span className="mark" aria-hidden="true">W</span>Warehouse Studio</div></header>
      <main>
        <p className="eyebrow">Workspace</p>
        <h1>Local service</h1>
        <section aria-labelledby="status-heading">
          <div className="status">
            <span className="indicator" aria-hidden="true" />
            <h2 id="status-heading">Startup complete</h2>
          </div>
          <dl><dt>Service address</dt><dd>{window.location.origin}</dd></dl>
          <p className="note">Keep the start window open while you work. To stop the service, press <kbd>Ctrl</kbd> + <kbd>C</kbd> in that window.</p>
        </section>
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
