"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ShieldCheck,
  LayoutDashboard,
  Files,
  ClipboardCheck,
  Network,
  BookOpen,
  History,
  Plug,
  Settings,
  ArrowUpRight,
  ArrowRight,
  ChevronRight,
  Search,
  Plus,
  Download,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Activity,
  RotateCcw,
  Wrench,
  Menu,
  X,
  Building2,
  Play,
} from "lucide-react";
import InvestigationWorkspace from "./investigation-workspace";
import IntegrationsWorkspace from "./integrations-workspace";
import IntakeWorkspace from "./intake-workspace";
import ReviewWorkspace from "./review-workspace";
import KnowledgeWorkspace from "./knowledge-workspace";
import PrintableExport from "./printable-export";
import AgentTrace from "./agent-trace";
import ClaimTable from "./claim-table";
import Evidence from "./evidence-viewer";
import ResolutionPanel from "./resolution-panel";
import AuditTimeline from "./audit-timeline";
import { money, label, Badge, Progress } from "./ui";
import {
  api,
  establish,
  roles,
  canWrite,
  Claim,
  Entry,
  Event,
} from "@/lib/api";

const nav = [
  ["Overview", "/dashboard", LayoutDashboard],
  ["Claims", "/claims", Files],
  ["Resolutions", "/resolutions", Wrench],
  ["Review", "/review", ClipboardCheck],
  ["Investigations", "/investigations", Network],
  ["Knowledge", "/knowledge", BookOpen],
  ["Audit trail", "/audit", History],
  ["Integrations", "/integrations", Plug],
  ["Administration", "/admin", Settings],
] as const;
function download(data: unknown, id: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = id + "-passport.json";
  a.click();
  URL.revokeObjectURL(url);
}

export default function Workspace() {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);
  const page = parts[0] || "dashboard";
  const claimId =
    page === "claims" && parts[1] && parts[1] !== "new" ? parts[1] : null;
  const [role, setRole] = useState("Claims Executive");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [current, setCurrent] = useState<Claim | null>(null);
  const [tasks, setTasks] = useState<Entry[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadedPath, setLoadedPath] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [step, setStep] = useState("");
  const [tab, setTab] = useState("Overview");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sort, setSort] = useState("id");
  const [pageNum, setPageNum] = useState(1);
  const [demoEpoch, setDemoEpoch] = useState(0);
  const activeRoute = useRef(pathname);
  activeRoute.current = pathname;
  const loadVersion = useRef(0);
  const actionLock = useRef(false);
  const load = useCallback(async () => {
    if (pathname !== activeRoute.current) return;
    const version = ++loadVersion.current;
    const route = activeRoute.current;
    setLoading(true);
    setLoadFailed(false);
    setError("");
    try {
      if (!sessionStorage.getItem("cg-token"))
        await establish(
          sessionStorage.getItem("cg-role") || "Claims Executive",
        );
      setRole(sessionStorage.getItem("cg-role") || "Claims Executive");
      const [all, ts, ev, c] = await Promise.all([
        api<Claim[]>("/claims"),
        api<Entry[]>("/resolutions"),
        api<Event[]>(
          "/audit?limit=200" + (claimId ? "&claim_id=" + claimId : ""),
        ),
        claimId ? api<Claim>("/claims/" + claimId) : Promise.resolve(null),
      ]);
      if (version !== loadVersion.current || route !== activeRoute.current)
        return;
      setClaims(all);
      setTasks(ts);
      setEvents(ev);
      setCurrent(c);
      setLoadedPath(route);
    } catch (e) {
      if (version === loadVersion.current && route === activeRoute.current) {
        setError((e as Error).message);
        setLoadFailed(true);
      }
    } finally {
      if (version === loadVersion.current && route === activeRoute.current)
        setLoading(false);
    }
  }, [claimId, pathname]);
  useEffect(() => {
    load();
    setTab("Overview");
    setMobile(false);
    setTaskId(null);
    setPageNum(1);
  }, [load, pathname]);
  async function action(fn: () => Promise<unknown>, message = "") {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      if (message) setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
      setStep("");
    }
  }
  async function switchRole(r: string) {
    await action(async () => {
      await establish(r);
      setRole(r);
    }, "Demo role updated. Permissions are enforced by the API.");
  }
  async function exportClaim() {
    if (!current) return;
    await action(async () => {
      download(await api("/claims/" + current.id + "/passport"), current.id);
    }, "Evidence passport exported.");
  }
  const filtered = claims
    .filter(
      (c) =>
        (status === "ALL" || c.status === status) &&
        [c.id, c.patient, c.hospital, c.procedure, c.data.payer, c.data.owner]
          .join(" ")
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "readiness"
        ? a.readiness - b.readiness
        : sort === "amount"
          ? b.amount - a.amount
          : a.id.localeCompare(b.id),
    );
  const ringColors = ["#298f88", "#d9b25e", "#7c9fb9", "#9b8bb1"];
  let ringCursor = 0;
  const ringStops = [
    "READY",
    "NEEDS_RESOLUTION",
    "HUMAN_REVIEW",
    "INVESTIGATION",
  ]
    .map((state, i) => {
      const start = ringCursor;
      ringCursor +=
        (claims.filter((c) => c.status === state).length /
          Math.max(claims.length, 1)) *
        100;
      return ringColors[i] + " " + start + "% " + ringCursor + "%";
    })
    .join(",");
  const selectedTask = tasks.find((t) => t.id === taskId);
  const selectedClaim = selectedTask
    ? claims.find((c) => c.id === selectedTask.claim_id)
    : null;
  const finding = current?.findings?.find((f) => f.id === parts[3]);
  const title =
    page === "dashboard"
      ? "Claim readiness, at a glance"
      : page === "claims"
        ? parts[1] === "new"
          ? "New claim intake"
          : "Claims workspace"
        : page === "resolutions"
          ? "Evidence resolution"
          : page === "audit"
            ? "Every action. Every source."
            : label(page);

  function filters() {
    return (
      <div className="filters">
        <label className="search">
          <Search size={16} />
          <input
            aria-label="Search claims"
            placeholder="Search claim, beneficiary, hospital…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPageNum(1);
            }}
          />
        </label>
        <select
          aria-label="Filter status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPageNum(1);
          }}
        >
          <option value="ALL">All statuses</option>
          {["READY", "NEEDS_RESOLUTION", "HUMAN_REVIEW", "INVESTIGATION"].map(
            (x) => (
              <option key={x}>{x}</option>
            ),
          )}
        </select>
        <select
          aria-label="Sort claims"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="id">Claim ID</option>
          <option value="readiness">Lowest readiness</option>
          <option value="amount">Highest amount</option>
        </select>
      </div>
    );
  }
  function table(list: Claim[]) {
    return <ClaimTable claims={list} />;
  }
  function timeline(list: Event[]) {
    return (
      <>
        <p className="muted">
          Current presentation activity. Prior sessions remain archived.
        </p>
        <AuditTimeline events={list} />
      </>
    );
  }
  function taskPanel(t: Entry, c: Claim) {
    return (
      <ResolutionPanel
        key={t.id}
        task={t}
        claim={c}
        role={role}
        busy={busy}
        step={step}
        action={action}
        onError={setError}
        onStep={setStep}
      />
    );
  }

  return (
    <div className="app">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <Link href="/dashboard" className="brand">
          <span className="brand-mark">
            <ShieldCheck size={25} />
          </span>
          <span>
            ClaimGuard<span className="brand-ai">AI</span>
            <small>READINESS INTELLIGENCE</small>
          </span>
        </Link>
        <div className="org">
          <span className="org-icon">
            <Building2 size={17} />
          </span>
          <div>
            Aster Grove<small>Hospital group · Demo workspace</small>
          </div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {nav.map(([name, url, Icon], i) => (
            <Link
              key={url}
              href={url}
              className={
                (page === url.slice(1) ? "active" : "") +
                (i === 8 ? " secondary" : "")
              }
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Resolutions" && (
                <b>{tasks.filter((t) => t.status !== "COMPLETED").length}</b>
              )}
              {i === 8 && <span className="later-dot" title="Later scope" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-note">
            <span className="live-dot" />
            DEMO ENVIRONMENT<p>Synthetic data. Real workflows.</p>
          </div>
          <div className="user">
            <span className="avatar">MS</span>
            <div>
              Meera Shah<small>{role}</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="utility">
          <button
            className="mobile-menu"
            onClick={() => setMobile(!mobile)}
            aria-label="Toggle navigation"
          >
            {mobile ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />{" "}
            <strong>
              {current
                ? current.id
                : page === "dashboard"
                  ? "Overview"
                  : label(page)}
            </strong>
          </div>
          <div className="utility-right">
            <button
              className="demo-reset"
              aria-label="Reset complete demo"
              title="Restore all 50 synthetic claims and archive additional intakes"
              disabled={busy || !canWrite(role)}
              onClick={() =>
                window.confirm(
                  "Reset presentation? Restore all 50 claims and tasks, clear current human decisions and archive imported claims and prior demo history.",
                ) &&
                action(async () => {
                  await api("/demo/reset-all", {});
                  for (const key of [
                    "cg-intake",
                    "cg-intake-identity",
                    "cg-analysis-job",
                  ])
                    sessionStorage.removeItem(key);
                  setDemoEpoch((v) => v + 1);
                }, "Presentation restored: 50 claims reset, tasks restored and human decisions cleared. Prior sessions archived.")
              }
            >
              <RotateCcw size={14} />
              <span>Reset presentation</span>
            </button>
            <span className="demo-pill">
              <span className="live-dot" />
              Demo mode
            </span>
            <label className="role-label">
              Demo role
              <select
                aria-label="Demo role"
                value={role}
                onChange={(e) => switchRole(e.target.value)}
                disabled={
                  busy || loading || Boolean(claimId && current?.id !== claimId)
                }
              >
                {roles.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <span className="avatar small">MS</span>
          </div>
        </header>
        <main>
          {error && (
            <div role="alert" className="error-banner">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button onClick={load}>Retry</button>
              <button
                onClick={() => {
                  sessionStorage.removeItem("cg-token");
                  load();
                }}
              >
                Reconnect session
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              <CheckCircle2 size={17} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={15} />
              </button>
            </div>
          )}
          {loading && (!claims.length || loadedPath !== pathname) ? (
            <div className="loading">
              <Activity />
              <h2>Opening your workspace</h2>
              <p>Loading persistent claims, evidence and audit history.</p>
            </div>
          ) : loadFailed ? (
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Workspace temporarily unavailable</h2>
                  <p>
                    Current claim state could not be verified. Retry above
                    before relying on a readiness result.
                  </p>
                </div>
                <AlertTriangle size={22} />
              </div>
            </section>
          ) : (
            <>
              {!current && (
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">
                      {page === "dashboard"
                        ? "OVERVIEW / COMMAND CENTER"
                        : "CLAIMGUARD WORKSPACE"}
                    </p>
                    <h1>{title}</h1>
                    <p>
                      {page === "dashboard"
                        ? "Prepare with confidence. Resolve with evidence. Keep every decision traceable."
                        : page === "resolutions"
                          ? "Close evidence gaps and move claims forward, with a complete audit trail."
                          : page === "claims"
                            ? parts[1] === "new"
                              ? "Upload sources, confirm identity and follow every check into the Claim Passport."
                              : "One queue for every claim. Clear next steps for every exception."
                            : page === "audit"
                              ? "A persistent record of agent execution, evidence and human action."
                              : page === "review"
                                ? "Resolve ambiguous findings with source-linked human decisions."
                                : page === "knowledge"
                                  ? "Governed sources, applicable dates and grounded retrieval."
                                  : page === "investigations"
                                    ? "Explore connected synthetic evidence. Every signal is an investigation lead."
                                    : page === "integrations"
                                      ? "Clear connection status and a working synthetic FHIR import."
                                      : "Synthetic demonstration workspace."}
                    </p>
                  </div>
                  <div className="heading-actions">
                    {page === "dashboard" && (
                      <span className="date">
                        03 October 2026
                        <br />
                        <small>Local synthetic demonstration</small>
                      </span>
                    )}
                    {["dashboard", "claims"].includes(page) && (
                      <Link className="button primary" href="/claims/new">
                        <Plus size={16} />
                        Load demo claim
                      </Link>
                    )}
                  </div>
                </div>
              )}
              {page === "dashboard" && (
                <>
                  <div className="metrics">
                    {[
                      [
                        "Claims in workspace",
                        claims.length,
                        "50 synthetic cases",
                        "navy",
                      ],
                      [
                        "Ready",
                        claims.filter((c) => c.status === "READY").length,
                        "Evidence complete",
                        "green",
                      ],
                      [
                        "Needs resolution",
                        claims.filter((c) => c.status === "NEEDS_RESOLUTION")
                          .length,
                        "Actionable evidence gaps",
                        "amber",
                      ],
                      [
                        "Human review",
                        claims.filter((c) => c.status === "HUMAN_REVIEW")
                          .length,
                        "Human judgment required",
                        "blue",
                      ],
                      [
                        "Investigation",
                        claims.filter((c) => c.status === "INVESTIGATION")
                          .length,
                        "Leads, not conclusions",
                        "purple",
                      ],
                    ].map(([name, value, sub, color]) => (
                      <div className={"metric " + color} key={name}>
                        <div className="metric-label">
                          {name}
                          <ArrowUpRight size={15} />
                        </div>
                        <strong>{value}</strong>
                        <small>{sub}</small>
                      </div>
                    ))}
                  </div>
                  <div className="demo-strip">
                    <div className="demo-icon">
                      <ShieldCheck size={24} />
                    </div>
                    <div>
                      <p className="eyebrow">THE EVIDENCE RESOLUTION STORY</p>
                      <h3>A missing report. A clear path to readiness.</h3>
                      <p>
                        Follow CG021 from 63% to 94% with validated evidence.
                      </p>
                    </div>
                    <Link className="button primary" href="/claims/CG021">
                      Open CG021
                      <ArrowRight size={17} />
                    </Link>
                  </div>
                  <nav
                    className="workflow-shortcuts"
                    aria-label="Synthetic workflow scenarios"
                  >
                    {[
                      ["CG001", "Clean · 98% READY"],
                      ["CG021", "Missing report · 63% → 94%"],
                      ["CG030", "Billing · human authority"],
                      ["CG048", "Network · investigation lead"],
                    ].map(([id, text]) => (
                      <Link key={id} href={"/claims/" + id}>
                        <strong>{id}</strong>
                        <span>{text}</span>
                        <ChevronRight size={15} />
                      </Link>
                    ))}
                  </nav>
                  <div className="dashboard-grid">
                    <section className="panel queue">
                      <div className="panel-head">
                        <div>
                          <h2>Claims requiring attention</h2>
                          <p>Prioritized by evidence gaps and review needs</p>
                        </div>
                        <Link href="/claims">
                          View all claims <ArrowUpRight size={15} />
                        </Link>
                      </div>
                      {table(
                        claims.filter((c) =>
                          [
                            "CG021",
                            "CG030",
                            "CG036",
                            "CG041",
                            "CG048",
                          ].includes(c.id),
                        ),
                      )}
                    </section>
                    <section className="panel readiness-panel">
                      <p className="eyebrow">OPERATIONAL HEALTH</p>
                      <h2>Readiness distribution</h2>
                      <div
                        className="readiness-ring"
                        style={{ background: `conic-gradient(${ringStops})` }}
                      >
                        <div>
                          <strong>
                            {Math.round(
                              claims.reduce((a, c) => a + c.readiness, 0) /
                                Math.max(claims.length, 1),
                            )}
                            <span>%</span>
                          </strong>
                          <small>average readiness</small>
                        </div>
                      </div>
                      <div className="distribution">
                        {[
                          "READY",
                          "NEEDS_RESOLUTION",
                          "HUMAN_REVIEW",
                          "INVESTIGATION",
                        ].map((s) => (
                          <div key={s}>
                            <span>
                              <span
                                className={"legend-dot " + s.toLowerCase()}
                              />
                              {label(s)}
                            </span>
                            <b>{claims.filter((c) => c.status === s).length}</b>
                          </div>
                        ))}
                      </div>
                      <p className="model-note">
                        Prototype operational model.
                        <br />
                        Not a probability of approval.
                      </p>
                    </section>
                  </div>
                  <div className="bottom-grid">
                    <section className="panel">
                      <div className="panel-head">
                        <h2>Recent activity</h2>
                        <Link href="/audit">
                          Full audit trail <ArrowUpRight size={15} />
                        </Link>
                      </div>
                      {timeline(events.slice(0, 4))}
                    </section>
                  </div>
                </>
              )}
              {page === "claims" && !claimId && parts[1] !== "new" && (
                <section className="panel">
                  {filters()}
                  {table(filtered.slice((pageNum - 1) * 12, pageNum * 12))}
                  <div className="pagination">
                    <span>
                      {filtered.length} claims · page {pageNum} of{" "}
                      {Math.max(1, Math.ceil(filtered.length / 12))}
                    </span>
                    <button
                      disabled={pageNum === 1}
                      onClick={() => setPageNum(pageNum - 1)}
                    >
                      Previous
                    </button>
                    <button
                      disabled={pageNum * 12 >= filtered.length}
                      onClick={() => setPageNum(pageNum + 1)}
                    >
                      Next
                    </button>
                  </div>
                </section>
              )}
              {page === "claims" && parts[1] === "new" && (
                <IntakeWorkspace key={demoEpoch} role={role} />
              )}
              {page === "review" && (
                <ReviewWorkspace key={demoEpoch} role={role} onChanged={load} />
              )}
              {page === "knowledge" && <KnowledgeWorkspace key={demoEpoch} />}
              {page === "investigations" && (
                <InvestigationWorkspace key={demoEpoch} />
              )}
              {page === "integrations" && (
                <IntegrationsWorkspace key={demoEpoch} role={role} />
              )}
              {current && parts[2] === "passport" && (
                <PrintableExport claimId={current.id} />
              )}
              {current &&
                parts[2] !== "evidence" &&
                parts[2] !== "passport" && (
                  <>
                    <div className="claim-heading">
                      <div>
                        <Link className="back-link" href="/claims">
                          Claims <ChevronRight size={13} />
                        </Link>
                        <div className="claim-title">
                          <h1>{current.id}</h1>
                          <Badge status={current.status} />
                        </div>
                        <p>
                          {current.patient} <span>·</span> {current.hospital}{" "}
                          <span>·</span> Synthetic beneficiary
                        </p>
                      </div>
                      <div className="actions">
                        <Link
                          className="button"
                          href={"/claims/" + current.id + "/passport"}
                        >
                          Print / PDF
                        </Link>
                        <button disabled={busy} onClick={exportClaim}>
                          <Download size={16} />
                          Export passport
                        </button>
                        {current.id === "CG021" && (
                          <button
                            disabled={busy || !canWrite(role)}
                            onClick={() =>
                              action(
                                () => api("/demo/reset", {}),
                                "CG021 reset to its initial synthetic state. Audit history retained.",
                              )
                            }
                          >
                            <RotateCcw size={15} />
                            Reset demo
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="claim-meta">
                      <div>
                        Procedure<strong>{current.procedure}</strong>
                      </div>
                      <div>
                        Payer<strong>{current.data.payer}</strong>
                      </div>
                      <div>
                        Admission → discharge
                        <strong>
                          {current.data.admission} → {current.data.discharge}
                        </strong>
                      </div>
                      <div>
                        Claim amount<strong>{money(current.amount)}</strong>
                      </div>
                      <div>
                        Owner<strong>{current.data.owner}</strong>
                      </div>
                    </div>
                    <section className="passport-hero">
                      <div className="passport-score">
                        <span className="eyebrow">CLAIM READINESS</span>
                        <strong key={current.readiness}>
                          {current.readiness}
                          <span>%</span>
                        </strong>
                        <Progress value={current.readiness} />
                      </div>
                      <div className="passport-copy">
                        <h2>
                          {current.status === "READY"
                            ? "Evidence ready. Human authority retained."
                            : current.status === "NEEDS_RESOLUTION"
                              ? "One evidence gap. A clear next step."
                              : current.status === "INVESTIGATION"
                                ? "A lead to examine. Evidence to verify."
                                : "Human judgment is needed."}
                        </h2>
                        <p>
                          {current.status === "NEEDS_RESOLUTION"
                            ? "A signed operative report is required by the applicable synthetic policy. Resolve the gap to unlock the updated passport."
                            : "Review the evidence, supporting sources and structured findings before downstream adjudication."}
                        </p>
                        <span className="model-note">
                          Prototype operational readiness model · Not
                          probability of approval
                        </span>
                      </div>
                      {current.status === "NEEDS_RESOLUTION" && (
                        <button
                          className="primary"
                          disabled={busy || !canWrite(role)}
                          onClick={() => {
                            setTaskId("RT-" + current.id);
                            document
                              .getElementById("resolution")
                              ?.scrollIntoView({ behavior: "smooth" });
                          }}
                        >
                          <Wrench size={16} />
                          Resolve evidence gap
                        </button>
                      )}
                    </section>
                    {current.tasks?.some(
                      (t) =>
                        t.status === "COMPLETED" &&
                        t.data.before === 63 &&
                        t.data.after === 94,
                    ) && (
                      <div className="readiness-transition" role="status">
                        <div>
                          <span>Before resolution</span>
                          <strong>63%</strong>
                        </div>
                        <ArrowRight size={22} />
                        <div>
                          <span>Validated evidence</span>
                          <strong>94% · READY</strong>
                        </div>
                        <p>
                          Operative report validated. Four dependent checks
                          reran; source and action history retained.
                        </p>
                        <button onClick={() => setTab("Audit")}>
                          Inspect audit history
                        </button>
                      </div>
                    )}
                    <div className="check-grid">
                      {Object.entries(current.data.checks).map(
                        ([key, value]) => (
                          <div
                            className={
                              "check-card " + (value >= 0.6 ? "pass" : "review")
                            }
                            key={key}
                          >
                            <div>
                              <span>
                                {key === "clinical"
                                  ? "Clinical consistency"
                                  : label(key)}
                              </span>
                              {value >= 0.6 ? (
                                <CheckCircle2 size={17} />
                              ) : (
                                <AlertTriangle size={17} />
                              )}
                            </div>
                            <strong>
                              {key === "documentation"
                                ? value === 1
                                  ? "COMPLETE"
                                  : "INCOMPLETE"
                                : key === "integrity"
                                  ? value === 0
                                    ? "INVESTIGATION LEAD"
                                    : "LOW SIGNAL"
                                  : value === 1
                                    ? "PASS"
                                    : value >= 0.6
                                      ? "CLEAR"
                                      : "REVIEW"}
                            </strong>
                            <small>
                              {Math.round(current.data.weights[key] * value)} /{" "}
                              {current.data.weights[key]} points
                            </small>
                          </div>
                        ),
                      )}
                    </div>
                    <div className="tabs" role="tablist">
                      {[
                        "Overview",
                        "Evidence Passport",
                        "Documents",
                        "Agent Trace",
                        "Human Decisions",
                        "Audit",
                      ].map((x) => (
                        <button
                          role="tab"
                          aria-selected={tab === x}
                          className={tab === x ? "selected" : ""}
                          key={x}
                          onClick={() => setTab(x)}
                        >
                          {x}
                        </button>
                      ))}
                    </div>
                    {tab === "Overview" && (
                      <>
                        <section className="panel findings">
                          <div className="panel-head">
                            <div>
                              <h2>
                                Open findings{" "}
                                <span className="count">
                                  {
                                    current.findings?.filter(
                                      (f) => f.status === "OPEN",
                                    ).length
                                  }
                                </span>
                              </h2>
                              <p>
                                Every finding links to its supporting source
                              </p>
                            </div>
                            <span className="subtle">
                              <ShieldCheck size={14} />
                              Source-grounded
                            </span>
                          </div>
                          {current.findings
                            ?.filter((f) => f.status === "OPEN")
                            .map((f) => (
                              <div className="finding-row" key={f.id}>
                                <span
                                  className={
                                    "finding-icon " +
                                    f.data.severity.toLowerCase()
                                  }
                                >
                                  <AlertTriangle size={19} />
                                </span>
                                <div>
                                  <div className="finding-title">
                                    <h3>{f.title}</h3>
                                    <span className="severity">
                                      {f.data.severity}
                                    </span>
                                  </div>
                                  <p>{f.data.description}</p>
                                  <small>
                                    {label(f.data.agent)} agent ·{" "}
                                    {f.data.evidence.length} source citation ·
                                    Rule {f.rule}
                                  </small>
                                </div>
                                <div className="finding-actions">
                                  <Link
                                    className="button"
                                    href={
                                      "/claims/" +
                                      current.id +
                                      "/evidence/" +
                                      f.id
                                    }
                                  >
                                    View evidence
                                    <ArrowUpRight size={15} />
                                  </Link>
                                  {f.rule === "F14" && (
                                    <button
                                      className="primary"
                                      disabled={busy || !canWrite(role)}
                                      onClick={() =>
                                        action(async () => {
                                          await api(
                                            "/findings/" + f.id + "/resolve",
                                            {},
                                          );
                                          setTaskId("RT-" + current.id);
                                        }, "Resolution task opened below.")
                                      }
                                    >
                                      <Wrench size={15} />
                                      Resolve
                                    </button>
                                  )}
                                </div>
                              </div>
                            ))}
                          {!current.findings?.some(
                            (f) => f.status === "OPEN",
                          ) && (
                            <div className="clear-state">
                              <CheckCircle2 size={29} />
                              <div>
                                <h3>No open findings</h3>
                                <p>
                                  Required evidence is complete. The passport is
                                  ready for downstream human review.
                                </p>
                              </div>
                            </div>
                          )}
                        </section>
                        <div id="resolution">
                          {current.tasks
                            ?.filter(
                              (t) =>
                                t.status !== "COMPLETED" || taskId === t.id,
                            )
                            .map((t) =>
                              taskPanel(
                                tasks.find((x) => x.id === t.id) || t,
                                current,
                              ),
                            )}
                        </div>
                        {current.data.cluster && (
                          <section className="panel">
                            <div className="panel-head">
                              <div>
                                <h2>Related synthetic claims</h2>
                                <p>
                                  Shared diagnostic fingerprint · Meridian
                                  Surgical Centre · Dr. A. Sen
                                </p>
                              </div>
                              <Badge status="INVESTIGATION" />
                            </div>
                            {table(claims.filter((c) => c.data.cluster))}
                            <p className="panel-footnote">
                              Six shared diagnostic hashes across six distinct
                              beneficiaries. This is a seeded investigation
                              lead; it does not establish fraud. Interactive
                              graph exploration is P2.
                            </p>
                          </section>
                        )}
                      </>
                    )}
                    {tab === "Evidence Passport" && (
                      <section className="panel evidence-passport">
                        <div className="panel-head">
                          <h2>Structured evidence passport</h2>
                          <button onClick={exportClaim}>
                            <Download size={15} />
                            Export JSON
                          </button>
                        </div>
                        {[
                          "Identity",
                          "Eligibility",
                          "Diagnosis",
                          "Procedure",
                          "Policy",
                          "Billing",
                          "Integrity",
                        ].map((x) => (
                          <div className="evidence-section" key={x}>
                            <ShieldCheck size={18} />
                            <div>
                              <h3>{x} evidence</h3>
                              <p>
                                {x === "Policy"
                                  ? "DemoCare Policy 2026 · synthetic · version 1.0 · effective 01 Jan–31 Dec 2026"
                                  : x === "Integrity"
                                    ? current.data.cluster
                                      ? "Shared diagnostic hash requires investigation"
                                      : "No seeded cross-claim reuse signal"
                                    : x === "Billing"
                                      ? current.data.line_items
                                          .map(
                                            (l) =>
                                              l.description +
                                              " " +
                                              money(l.amount),
                                          )
                                          .join(" · ")
                                      : `${current.patient} · ${current.procedure} · source documents below`}
                              </p>
                              <small>
                                Deterministic demo evaluation · claim{" "}
                                {current.id} · source provenance retained
                              </small>
                            </div>
                          </div>
                        ))}
                        <h3>Available source documents</h3>
                        {current.documents?.map((d) => (
                          <details className="source-detail" key={d.id}>
                            <summary>
                              {d.title} · page 1 · version {d.data.version}
                            </summary>
                            <pre className="document-text">{d.text}</pre>
                            <p className="hash">SHA-256 {d.hash}</p>
                          </details>
                        ))}
                        <details className="source-detail">
                          <summary>Readiness breakdown and hard gates</summary>
                          <pre className="document-text">
                            {JSON.stringify(
                              {
                                weights: current.data.weights,
                                checks: current.data.checks,
                                hard_gates: [
                                  "Missing core report prevents READY",
                                  "Inactive policy caps readiness at 49",
                                  "Identity conflict caps readiness at 39",
                                ],
                                assumptions:
                                  "Baseline integrity contributes 3/5. CG021 retains a 4-point billing reserve after resolution.",
                              },
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      </section>
                    )}
                    {tab === "Documents" && (
                      <section className="panel documents">
                        <h2>Claim source documents</h2>
                        {current.documents?.map((d) => (
                          <details className="source-detail" key={d.id}>
                            <summary>
                              <FileText size={18} />
                              {d.title}
                              <span>
                                {d.data.validated
                                  ? "Validated"
                                  : "Pending validation"}{" "}
                                · page 1
                              </span>
                            </summary>
                            <pre className="document-text">{d.text}</pre>
                            <p className="hash">Fingerprint: {d.hash}</p>
                          </details>
                        ))}
                      </section>
                    )}
                    {tab === "Agent Trace" && (
                      <section className="panel">
                        <div className="panel-head">
                          <h2>Structured execution trace</h2>
                          <button
                            disabled={!canWrite(role) || busy}
                            onClick={() =>
                              action(
                                () =>
                                  api("/claims/" + current.id + "/analyse", {}),
                                "Deterministic checks rerun.",
                              )
                            }
                          >
                            <Play size={15} />
                            Rerun analysis
                          </button>
                        </div>
                        <p className="panel-footnote">
                          Deterministic check execution; no live model agents.
                          Structured metadata and evidence-backed outputs only.
                        </p>
                        <AgentTrace
                          steps={(current.runs || []).slice(-16).map((r) => ({
                            agent: r.agent,
                            ...r.data,
                            status: r.data.status,
                          }))}
                        />
                      </section>
                    )}
                    {tab === "Human Decisions" && (
                      <section className="panel">
                        <h2>Human decisions</h2>
                        {!current.decisions?.length && (
                          <div className="empty">
                            No decisions recorded. Review a finding in the
                            evidence viewer to record a disposition.
                          </div>
                        )}
                        {current.decisions?.map((d) => (
                          <div className="decision" key={d.id}>
                            <strong>
                              {d.data.decision} · {d.data.reviewer}
                            </strong>
                            <p>{d.data.reason}</p>
                            <small>{d.data.timestamp}</small>
                          </div>
                        ))}
                      </section>
                    )}
                    {tab === "Audit" && (
                      <section className="panel">
                        <div className="panel-head">
                          <h2>Claim audit timeline</h2>
                          <span>Persistent · UTC stored / IST displayed</span>
                        </div>
                        {timeline(events)}
                      </section>
                    )}
                  </>
                )}
              {current &&
                parts[2] === "evidence" &&
                (finding ? (
                  <Evidence
                    current={current}
                    finding={finding}
                    role={role}
                    busy={busy}
                    onDecision={(decision, reason) =>
                      action(
                        () =>
                          api("/findings/" + finding.id + "/decision", {
                            decision,
                            reason,
                          }),
                        "Human decision saved. Original source and finding retained.",
                      )
                    }
                  />
                ) : (
                  <div className="empty">
                    Finding not found.{" "}
                    <Link href={"/claims/" + current.id}>
                      Return to passport
                    </Link>
                  </div>
                ))}
              {page === "resolutions" && (
                <>
                  {selectedTask && selectedClaim ? (
                    taskPanel(selectedTask, selectedClaim)
                  ) : (
                    <section className="panel">
                      <div className="panel-head">
                        <h2>Resolution queue</h2>
                        <span>
                          {tasks.filter((t) => t.status !== "COMPLETED").length}{" "}
                          open evidence gaps
                        </span>
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Task / claim</th>
                              <th>Required evidence</th>
                              <th>Owner</th>
                              <th>Status</th>
                              <th />
                            </tr>
                          </thead>
                          <tbody>
                            {tasks.map((t) => (
                              <tr key={t.id}>
                                <td>
                                  <Link
                                    className="claim-link"
                                    href={"/claims/" + t.claim_id}
                                  >
                                    {t.claim_id}
                                  </Link>
                                  <small>{t.id}</small>
                                </td>
                                <td>
                                  Signed operative report
                                  <small>Originating agent: Evidence</small>
                                </td>
                                <td>{t.data.owner}</td>
                                <td>
                                  <Badge status={t.status} />
                                </td>
                                <td>
                                  <button onClick={() => setTaskId(t.id)}>
                                    Open task
                                    <ArrowUpRight size={15} />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  )}
                </>
              )}
              {page === "audit" && (
                <section className="panel">
                  <div className="filters">
                    <label className="search">
                      <Search size={16} />
                      <input
                        aria-label="Search audit history"
                        placeholder="Filter by claim, actor or event…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                    <span>Latest 100 matching events · IST</span>
                  </div>
                  {timeline(
                    events.filter((e) =>
                      [e.claim_id, e.actor, e.event]
                        .join(" ")
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                    ),
                  )}
                </section>
              )}
              {page === "admin" && (
                <section className="panel later">
                  <span className="coming">Coming later ? Administration</span>
                  <h2>Production administration is outside this demo scope</h2>
                  <p>
                    Current role permissions are enforced by the API. Governed
                    source metadata is available in Knowledge; production user
                    management and rule configuration require a later release.
                  </p>
                  <Link className="button primary" href="/knowledge">
                    Open Knowledge Center
                    <ArrowRight size={16} />
                  </Link>
                </section>
              )}
            </>
          )}
          <footer>
            <span>
              <ShieldCheck size={13} />
              ClaimGuard prepares evidence. Humans retain decision authority.
            </span>
            <span>All patients, providers and policies are synthetic.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
