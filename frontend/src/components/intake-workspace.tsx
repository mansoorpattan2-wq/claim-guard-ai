"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Play,
} from "lucide-react";
import {
  api,
  uploadFiles,
  IntakePreview,
  AnalysisJob,
  canWrite,
} from "@/lib/api";
import { Badge } from "./ui";
import AgentTrace from "./agent-trace";

const kinds = [
  "operative_report",
  "discharge_summary",
  "final_bill",
  "policy",
  "diagnostic_report",
  "pre_authorisation",
  "unknown",
];
const stages = [
  "Reading documents",
  "Validating eligibility",
  "Checking evidence",
  "Retrieving policy",
  "Checking clinical consistency",
  "Checking billing",
  "Checking integrity signals",
  "Preparing Claim Passport",
];
export default function IntakeWorkspace({ role }: { role: string }) {
  const input = useRef<HTMLInputElement>(null);
  const actionLock = useRef(false);
  const [mode, setMode] = useState("upload");
  const [intake, setIntake] = useState<IntakePreview | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [identity, setIdentity] = useState({
    patient: "",
    hospital: "",
    procedure: "Laparoscopic appendectomy",
    payer: "DemoCare Health",
    doctor: "",
    admission: "2026-10-01",
    discharge: "2026-10-03",
    amount: "78000",
    policy_active: true,
  });
  useEffect(() => {
    const id = sessionStorage.getItem("cg-intake");
    if (!id) return;
    api<IntakePreview>("/intakes/" + id)
      .then(async (item) => {
        if (item.status === "ARCHIVED") {
          sessionStorage.removeItem("cg-intake");
          return;
        }
        setIntake(item);
        const saved = sessionStorage.getItem("cg-intake-identity");
        if (saved) setIdentity(JSON.parse(saved));
        const jid = sessionStorage.getItem("cg-analysis-job");
        if (jid) setJob(await api<AnalysisJob>("/analysis-jobs/" + jid));
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!job || !["QUEUED", "RUNNING"].includes(job.status)) return;
    let stopped = false;
    const timer = setTimeout(async () => {
      try {
        const next = await api<AnalysisJob>("/analysis-jobs/" + job.id);
        if (!stopped) setJob(next);
      } catch (e) {
        if (!stopped) setError((e as Error).message);
      }
    }, 350);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [job]);
  async function upload(files: File[]) {
    if (!files.length || actionLock.current || !canWrite(role)) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    setProgress(0);
    try {
      let item = intake;
      if (!item) item = await api<IntakePreview>("/intakes", {});
      sessionStorage.setItem("cg-intake", item.id);
      setIntake(item);
      const result = await uploadFiles(
        "/intakes/" + item.id + "/files",
        files,
        setProgress,
      );
      setIntake(result);
      setConfirmed(false);
      const map: Record<string, string> = {
        Beneficiary: "patient",
        Hospital: "hospital",
        Procedure: "procedure",
        Payer: "payer",
        Doctor: "doctor",
        Admission: "admission",
        Discharge: "discharge",
        Amount: "amount",
      };
      setIdentity((old) => {
        const next = { ...old };
        for (const [key, value] of Object.entries(result.identity)) {
          const target = map[key];
          if (target) (next as Record<string, unknown>)[target] = value;
        }
        return next;
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }
  async function analyse() {
    if (!intake || actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    try {
      sessionStorage.setItem("cg-intake-identity", JSON.stringify(identity));
      const result = await api<AnalysisJob>(
        "/intakes/" + intake.id + "/analyse",
        {
          ...identity,
          amount: Number(identity.amount),
          doctor: identity.doctor || "Unspecified provider",
        },
      );
      sessionStorage.setItem("cg-analysis-job", result.id);
      setJob(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <div className="feature-tabs">
        <button
          className={mode === "upload" ? "selected" : ""}
          onClick={() => setMode("upload")}
        >
          Upload claim
        </button>
        <button
          className={mode === "demo" ? "selected" : ""}
          onClick={() => setMode("demo")}
        >
          Load synthetic demo
        </button>
        <Link href="/integrations">
          FHIR sandbox import <ArrowRight size={14} />
        </Link>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={16} />
          {error}
          <button
            onClick={async () => {
              setError("");
              if (job) {
                try {
                  setJob(await api<AnalysisJob>("/analysis-jobs/" + job.id));
                } catch (e) {
                  setError((e as Error).message);
                }
              } else input.current?.click();
            }}
          >
            Retry
          </button>
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      {mode === "demo" ? (
        <section className="panel demo-loader">
          <p className="eyebrow">DETERMINISTIC DEMO SCENARIOS</p>
          <h2>Choose a claim story</h2>
          <div className="scenario-grid">
            {[
              [
                "CG021",
                "Missing operative report",
                "63% → resolution → 94% READY",
              ],
              ["CG001", "Clean evidence passport", "98% · READY"],
              [
                "CG030",
                "Package billing review",
                "Source-backed anaesthesia finding",
              ],
              [
                "CG048",
                "Investigation network",
                "Connected synthetic anomaly leads",
              ],
            ].map(([id, name, description]) => (
              <Link className="scenario" href={"/claims/" + id} key={id}>
                <span className="eyebrow">{id}</span>
                <h3>{name}</h3>
                <p>{description}</p>
                <span>
                  Open passport <ArrowRight size={15} />
                </span>
              </Link>
            ))}
          </div>
        </section>
      ) : (
        <>
          {!job && (
            <section className="panel intake-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">01 / DOCUMENTS</p>
                  <h2>Bring the evidence together</h2>
                  <p>
                    TXT, text PDF and DOCX extraction · images retained for
                    manual review · 2 MB per file
                  </p>
                </div>
                <span>Synthetic data only</span>
              </div>
              <div
                className={"dropzone " + (busy ? "uploading" : "")}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  upload(Array.from(e.dataTransfer.files));
                }}
              >
                <Upload size={28} />
                <h3>Drop claim documents here</h3>
                <p>
                  Up to 20 files. Classifications can be corrected before
                  analysis.
                </p>
                <button
                  disabled={busy || !canWrite(role)}
                  onClick={() => input.current?.click()}
                >
                  Choose documents
                </button>
                <input
                  ref={input}
                  type="file"
                  multiple
                  hidden
                  accept=".txt,.pdf,.docx,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    upload(Array.from(e.target.files || []));
                    e.target.value = "";
                  }}
                />
                {busy && (
                  <div role="status" className="upload-progress">
                    <progress value={progress} max={100} />
                    <span>Uploading documents · {progress}%</span>
                  </div>
                )}
              </div>
              {intake?.files.map((f) => (
                <div className="intake-file" key={f.id}>
                  <FileText size={20} />
                  <div>
                    <strong>{f.data.filename}</strong>
                    <small>
                      {Math.ceil(f.data.size / 1024)} KB ·{" "}
                      {f.data.extraction_status === "PARSED"
                        ? "Text extracted"
                        : "Unreadable — clearer text required"}
                    </small>
                  </div>
                  <select
                    aria-label={"Classification " + f.data.filename}
                    value={f.kind}
                    disabled={busy || !canWrite(role)}
                    onChange={async (e) => {
                      setBusy(true);
                      try {
                        setIntake(
                          await api<IntakePreview>(
                            "/intakes/" +
                              intake.id +
                              "/files/" +
                              f.id +
                              "/classification",
                            { kind: e.target.value },
                          ),
                        );
                      } catch (err) {
                        setError((err as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {kinds.map((k) => (
                      <option key={k} value={k}>
                        {k.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                  {f.data.extraction_status === "PARSED" ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <AlertTriangle size={17} />
                  )}
                </div>
              ))}
              {intake && (
                <div className="identity-preview">
                  <p className="eyebrow">02 / IDENTITY PREVIEW</p>
                  <h2>Confirm documented claim details</h2>
                  <p>
                    Extracted values populate this form. Default demo dates and
                    package amounts are editable and require your confirmation.
                  </p>
                  {intake.conflicts.length > 0 && (
                    <div className="error-banner">
                      Conflicting fields: {intake.conflicts.join(", ")}. These
                      will route to human review.
                    </div>
                  )}
                  <div className="identity-form">
                    {(
                      [
                        "patient",
                        "hospital",
                        "procedure",
                        "payer",
                        "doctor",
                        "admission",
                        "discharge",
                        "amount",
                      ] as const
                    ).map((key) => (
                      <label key={key}>
                        {key === "patient"
                          ? "Beneficiary alias"
                          : key[0].toUpperCase() + key.slice(1)}
                        <input
                          aria-label={"Intake " + key}
                          type={
                            key === "admission" || key === "discharge"
                              ? "date"
                              : key === "amount"
                                ? "number"
                                : "text"
                          }
                          value={identity[key]}
                          onChange={(e) => {
                            setConfirmed(false);
                            setIdentity({ ...identity, [key]: e.target.value });
                          }}
                        />
                      </label>
                    ))}
                  </div>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={identity.policy_active}
                      onChange={(e) => {
                        setConfirmed(false);
                        setIdentity({
                          ...identity,
                          policy_active: e.target.checked,
                        });
                      }}
                    />
                    Policy active on admission — confirm against supplied
                    evidence
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(e) => setConfirmed(e.target.checked)}
                    />
                    I confirm these are synthetic claim details and the fields
                    above reflect the supplied evidence.
                  </label>
                  <button
                    className="primary"
                    disabled={
                      busy ||
                      !canWrite(role) ||
                      !confirmed ||
                      !identity.patient ||
                      !identity.hospital ||
                      !identity.amount
                    }
                    onClick={analyse}
                  >
                    <Play size={16} />
                    Analyse Claim
                  </button>
                </div>
              )}
            </section>
          )}
          {job && (
            <section className="panel analysis-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">PERSISTENT ANALYSIS / {job.id}</p>
                  <h2>
                    {job.status === "COMPLETED"
                      ? "Analysis complete"
                      : job.status === "FAILED"
                        ? "A check needs attention"
                        : "Preparing your Claim Passport"}
                  </h2>
                </div>
                <Badge status={job.status} />
              </div>
              <div className="execution-progress" role="status">
                {stages.map((name, i) => {
                  const completed = job.data.steps.some(
                    (s) => s.agent === name && s.status === "COMPLETED",
                  );
                  return (
                    <div
                      key={name}
                      className={
                        completed
                          ? "done"
                          : i === job.data.current_step &&
                              job.status === "RUNNING"
                            ? "running"
                            : ""
                      }
                    >
                      <span>
                        {completed ? (
                          <CheckCircle2 size={17} />
                        ) : job.status === "FAILED" &&
                          name === job.data.failed_step ? (
                          <AlertTriangle size={17} />
                        ) : (
                          i + 1
                        )}
                      </span>
                      <strong>{name}</strong>
                      <small>
                        {completed
                          ? "Complete"
                          : job.status === "FAILED" &&
                              name === job.data.failed_step
                            ? "Failed"
                            : "Pending"}
                      </small>
                    </div>
                  );
                })}
              </div>
              {job.data.error && (
                <div className="error-banner" role="alert">
                  {job.data.error}
                  <button
                    disabled={!canWrite(role) || busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const next = await api<AnalysisJob>(
                          "/analysis-jobs/" + job.id + "/retry",
                          {},
                        );
                        sessionStorage.setItem("cg-analysis-job", next.id);
                        setJob(next);
                        setError("");
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Retry analysis
                  </button>
                </div>
              )}
              <AgentTrace steps={job.data.steps} />
              <div className="actions panel-actions">
                {job.status === "COMPLETED" && (
                  <Link
                    className="button primary"
                    href={"/claims/" + job.claim_id}
                  >
                    Open Claim Passport
                    <ArrowRight size={16} />
                  </Link>
                )}
                {job.status === "FAILED" && (
                  <Link className="button" href={"/claims/" + job.claim_id}>
                    Open human review passport
                  </Link>
                )}
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}
