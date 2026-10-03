"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "./ui";
import { BookOpen, Search, AlertTriangle } from "lucide-react";
type Source = {
  id: string;
  title: string;
  status: string;
  chunk_count: number;
  data: {
    authority: string;
    version: string;
    effective_date: string;
    expiry_date: string;
    retrieval: string;
  };
};
type Passage = {
  id: string;
  text: string;
  source: string;
  title: string;
  authority: string;
  version: string;
  page: number;
  section: string;
  score: number;
  rank: number;
  effective_date: string;
  expiry_date: string;
  matched_terms: string[];
};
type Retrieval = {
  answer: string;
  status: string;
  passages: Passage[];
  citations: string[];
  applicable_date: string;
  method: string;
};
export default function KnowledgeWorkspace() {
  const [sources, setSources] = useState<Source[]>([]);
  const [query, setQuery] = useState(
    "Is anaesthesia separately billable for demo package LAP-APP-01?",
  );
  const [date, setDate] = useState("2026-10-02");
  const [result, setResult] = useState<Retrieval | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function loadSources() {
    setError("");
    return api<Source[]>("/knowledge/catalog")
      .then(setSources)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    loadSources();
  }, []);
  async function retrieve() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await api<Retrieval>("/knowledge/retrieve", {
          query,
          applicable_date: date,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={17} />
          {error}
          <button
            disabled={busy}
            onClick={() => (sources.length ? retrieve() : loadSources())}
          >
            Retry
          </button>
        </div>
      )}
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Governed knowledge sources</h2>
            <p>Authority, applicability and version precede interpretation.</p>
          </div>
          <BookOpen size={20} />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Knowledge source / authority</th>
                <th>Version</th>
                <th>Effective dates</th>
                <th>Status</th>
                <th>Chunks</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.title}</strong>
                    <small>{s.data.authority}</small>
                  </td>
                  <td>{s.data.version}</td>
                  <td>
                    {s.data.effective_date} → {s.data.expiry_date}
                  </td>
                  <td>
                    <Badge status={s.status} />
                  </td>
                  <td>{s.chunk_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel retrieval-panel">
        <p className="eyebrow">RETRIEVAL TEST / JUDGE DEMO</p>
        <h2>Ask a question. Inspect its grounding.</h2>
        <p>
          Deterministic keyword ranking with organisation, active-source and
          effective-date filters. Vector search and model synthesis are not
          connected.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            retrieve();
          }}
        >
          <label>
            Policy question
            <input
              aria-label="Policy question"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
              minLength={3}
            />
          </label>
          <label>
            Applicable date
            <input
              aria-label="Applicable date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            <Search size={16} />
            {busy ? "Retrieving sources…" : "Test retrieval"}
          </button>
        </form>
        {result && (
          <>
            <div
              className={
                "grounded-answer " +
                (result.status === "GROUNDED" ? "supported" : "")
              }
              role="status"
            >
              <p className="eyebrow">
                {result.status} / APPLICABLE {result.applicable_date}
              </p>
              <h3>{result.answer}</h3>
              <small>
                Citations:{" "}
                {result.citations.join(", ") || "No supported answer"} ·{" "}
                {result.method}
              </small>
            </div>
            <h3>Ranked passages · {result.passages.length}</h3>
            {result.passages.map((p) => (
              <div className="citation-card" key={p.id}>
                <div className="citation-rank">
                  <span>
                    #{p.rank} · score {p.score.toFixed(3)}
                  </span>
                  <b>{p.id}</b>
                </div>
                <h3>
                  {p.source} / {p.section} · {p.title}
                </h3>
                <blockquote>{p.text}</blockquote>
                <small>
                  {p.authority} · v{p.version} · page {p.page} ·{" "}
                  {p.effective_date} → {p.expiry_date}
                </small>
                <p className="matched-terms">
                  Matched terms: {p.matched_terms.join(", ")}
                </p>
              </div>
            ))}
          </>
        )}
      </section>
    </>
  );
}
