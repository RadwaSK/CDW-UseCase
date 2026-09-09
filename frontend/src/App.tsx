import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [health, setHealth] = useState<string>("checking...");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(`${data.status} (database: ${data.database})`))
      .catch(() => setHealth("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "2rem auto" }}>
      <p style={{ background: "#fff3cd", padding: "0.5rem 1rem", borderRadius: 4 }}>
        Local development demo — synthetic sample data, single-user, no authentication.
      </p>
      <h1>Enterprise Modernization Assessment & Change Orchestrator</h1>
      <p>
        A technical demonstration of a safe, stateful multi-agent workflow for legacy-application
        modernization assessment. This is not an official CDW product.
      </p>
      <p>Backend health: {health}</p>
      <p style={{ color: "#666" }}>
        Assessment form, progress view, report, and trace panel are added in later phases.
      </p>
    </main>
  );
}

export default App;
