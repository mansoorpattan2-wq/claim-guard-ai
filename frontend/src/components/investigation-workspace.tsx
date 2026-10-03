"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Claim } from "@/lib/api";
import {
  Network,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ArrowUpRight,
  AlertTriangle,
} from "lucide-react";
import ClaimTable from "./claim-table";
type Node = {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  data: Record<string, unknown>;
};
type Graph = {
  status: string;
  nodes: Node[];
  edges: { source: string; target: string; label: string }[];
  signals: {
    id: string;
    title: string;
    observed: string | number;
    baseline: string | number;
    detail: string;
    evidence: unknown;
  }[];
  claims: Claim[];
  adapter: string;
};
const colors: Record<string, string> = {
  Hospital: "#416a80",
  Doctor: "#468d92",
  Procedure: "#619e8d",
  Claim: "#7d9b91",
  Document: "#a88f6a",
  Invoice: "#ad9475",
};
export default function InvestigationWorkspace() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [selected, setSelected] = useState("CG048");
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState("");
  async function load() {
    try {
      setError("");
      setGraph(await api<Graph>("/investigations/graph"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const node = graph?.nodes.find((n) => n.id === selected);
  return (
    <>
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={17} />
          {error}
          <button onClick={load}>Retry graph</button>
        </div>
      )}
      {!graph && !error ? (
        <section className="panel">
          <p className="empty">
            Loading organisation-scoped integrity evidence…
          </p>
        </section>
      ) : (
        graph && (
          <>
            <div className="investigation-notice">
              <Network size={21} />
              <div>
                <strong>INVESTIGATION LEAD</strong>
                <p>
                  Patterns warrant verification. They do not establish fraud or
                  determine claim denial.
                </p>
              </div>
              <span>CG045–CG050 · deterministic synthetic network</span>
            </div>
            <div className="signal-grid">
              {graph.signals.map((signal) => (
                <section className="signal-card" key={signal.id}>
                  <p className="eyebrow">{signal.id} / INTEGRITY SIGNAL</p>
                  <h3>{signal.title}</h3>
                  <strong>{signal.observed}</strong>
                  <small>Comparison: {signal.baseline}</small>
                  <p>{signal.detail}</p>
                  <details>
                    <summary>Inspect supporting evidence</summary>
                    <pre className="document-text">
                      {JSON.stringify(signal.evidence, null, 2)}
                    </pre>
                  </details>
                </section>
              ))}
            </div>
            <div className="graph-layout">
              <section className="panel graph-panel">
                <div className="panel-head">
                  <div>
                    <h2>Connected evidence network</h2>
                    <p>
                      Select a node to inspect its evidence. Claims link to
                      their passports.
                    </p>
                  </div>
                  <div className="graph-controls">
                    <label>
                      Focus
                      <select
                        aria-label="Focus claim"
                        value={selected.startsWith("CG") ? selected : "all"}
                        onChange={(e) => setSelected(e.target.value)}
                      >
                        <option value="all">All nodes</option>
                        {graph.claims.map((c) => (
                          <option key={c.id}>{c.id}</option>
                        ))}
                      </select>
                    </label>
                    <button
                      aria-label="Zoom in graph"
                      onClick={() => setZoom(Math.min(1.6, zoom + 0.15))}
                    >
                      <ZoomIn size={16} />
                    </button>
                    <button
                      aria-label="Zoom out graph"
                      onClick={() => setZoom(Math.max(0.7, zoom - 0.15))}
                    >
                      <ZoomOut size={16} />
                    </button>
                    <button
                      aria-label="Reset graph view"
                      onClick={() => {
                        setZoom(1);
                        setSelected("CG048");
                      }}
                    >
                      <RotateCcw size={15} />
                    </button>
                  </div>
                </div>
                <div className="graph-canvas">
                  <svg
                    viewBox="0 0 1260 580"
                    role="group"
                    aria-label="Hospital to doctor, procedure, six claims and shared document network"
                  >
                    <defs>
                      <pattern
                        id="graph-grid"
                        width="24"
                        height="24"
                        patternUnits="userSpaceOnUse"
                      >
                        <circle cx="2" cy="2" r="1" fill="#e2e9e8" />
                      </pattern>
                    </defs>
                    <rect width="1260" height="580" fill="url(#graph-grid)" />
                    <g
                      transform={`translate(${(1 - zoom) * 600},${(1 - zoom) * 280}) scale(${zoom})`}
                    >
                      {graph.edges.map((edge, i) => {
                        const a = graph.nodes.find((n) => n.id === edge.source);
                        const b = graph.nodes.find((n) => n.id === edge.target);
                        if (!a || !b) return null;
                        const emphasis =
                          edge.source === selected || edge.target === selected;
                        return (
                          <path
                            key={i}
                            d={`M ${a.x + 155} ${a.y + 25} C ${a.x + 205} ${a.y + 25}, ${b.x - 40} ${b.y + 25}, ${b.x} ${b.y + 25}`}
                            stroke={emphasis ? "#318c85" : "#c3d3d1"}
                            strokeWidth={emphasis ? 2.4 : 1.2}
                            fill="none"
                          >
                            <title>{edge.label}</title>
                          </path>
                        );
                      })}
                      {graph.nodes.map((n) => (
                        <g
                          key={n.id}
                          className={
                            "graph-node " +
                            (selected === n.id ? "selected" : "")
                          }
                          transform={`translate(${n.x},${n.y})`}
                          role="button"
                          tabIndex={0}
                          aria-label={n.type + " " + n.label}
                          onClick={() => setSelected(n.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelected(n.id);
                            }
                          }}
                        >
                          <rect
                            width="165"
                            height="54"
                            rx="6"
                            fill="white"
                            stroke={selected === n.id ? "#278b7d" : "#cbdad6"}
                            strokeWidth={selected === n.id ? 2 : 1}
                          />
                          <rect
                            x="0"
                            y="12"
                            width="3"
                            height="29"
                            fill={colors[n.type]}
                            rx="1"
                          />
                          <text
                            x="12"
                            y="17"
                            fontSize="10"
                            letterSpacing="1"
                            fill={colors[n.type]}
                          >
                            {n.type.toUpperCase()}
                          </text>
                          <text
                            x="12"
                            y="35"
                            fontSize="14"
                            fill="#385962"
                            fontWeight="600"
                          >
                            {n.label.length > 25
                              ? n.label.slice(0, 24) + "…"
                              : n.label}
                          </text>
                          <title>{n.label}</title>
                        </g>
                      ))}
                    </g>
                  </svg>
                </div>
                <div className="graph-legend">
                  {Object.entries(colors).map(([type, color]) => (
                    <span key={type}>
                      <i style={{ background: color }} />
                      {type}
                    </span>
                  ))}
                </div>
                <p className="panel-footnote">{graph.adapter}</p>
              </section>
              <section className="panel graph-detail">
                <p className="eyebrow">SELECTED EVIDENCE NODE</p>
                {node ? (
                  <>
                    <span className="node-type">{node.type}</span>
                    <h2>{node.label}</h2>
                    {Object.entries(node.data).map(([key, value]) => (
                      <div className="node-field" key={key}>
                        <small>{key.replaceAll("_", " ")}</small>
                        <strong>
                          {Array.isArray(value)
                            ? value.join(" · ")
                            : typeof value === "object"
                              ? JSON.stringify(value)
                              : String(value)}
                        </strong>
                      </div>
                    ))}
                    {node.type === "Claim" && (
                      <Link
                        className="button primary"
                        href={"/claims/" + node.id}
                      >
                        Open Claim Passport
                        <ArrowUpRight size={15} />
                      </Link>
                    )}
                  </>
                ) : (
                  <p>Select a graph node to inspect supporting evidence.</p>
                )}
              </section>
            </div>
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Linked claims</h2>
                  <p>
                    Shared diagnostic source and provider / procedure context
                  </p>
                </div>
                <span>INVESTIGATION LEAD</span>
              </div>
              <ClaimTable claims={graph.claims} />
            </section>
          </>
        )
      )}
    </>
  );
}
