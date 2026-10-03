"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, AnalysisJob, canWrite } from "@/lib/api";
import {
  Plug,
  Play,
  FileJson,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Download,
} from "lucide-react";
import { Badge } from "./ui";
type Integration = {
  id: string;
  name: string;
  status: string;
  detail: string;
  testable: boolean;
};
type ImportResult = AnalysisJob & {
  mapping: {
    patient: string;
    provider: string;
    payer: string;
    amount: number;
    documents: number;
  };
  adapter: string;
};
export default function IntegrationsWorkspace({ role }: { role: string }) {
  const [items, setItems] = useState<Integration[]>([]);
  const [text, setText] = useState("");
  const [job, setJob] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const actionLock = useRef(false);
  function load() {
    setError("");
    return api<Integration[]>("/integrations")
      .then(setItems)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (!job || !["QUEUED", "RUNNING"].includes(job.status)) return;
    const timer = setTimeout(async () => {
      try {
        const result = await api<AnalysisJob>("/analysis-jobs/" + job.id);
        setJob((old) => (old ? { ...old, ...result } : null));
      } catch (e) {
        setError((e as Error).message);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [job]);
  async function perform(fn: () => Promise<void>) {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }
  function saveSample() {
    const url = URL.createObjectURL(
      new Blob([text], { type: "application/fhir+json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "claimguard-synthetic-fhir-r4.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={17} />
          {error}
          <button onClick={load}>Retry connection status</button>
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </div>
      )}
      <div className="integration-grid">
        {items.map((item) => (
          <section className="panel integration-card" key={item.id}>
            <div>
              <span className="integration-icon">
                {item.id === "fhir" ? (
                  <FileJson size={22} />
                ) : (
                  <Plug size={22} />
                )}
              </span>
              <span
                className={
                  "integration-status " +
                  (item.status === "Not Connected" ? "disconnected" : "")
                }
              >
                {item.status}
              </span>
            </div>
            <h2>{item.name}</h2>
            <p>{item.detail}</p>
            {item.testable ? (
              <button
                disabled={busy || !canWrite(role)}
                onClick={() =>
                  perform(async () => {
                    const result = await api<{ message: string }>(
                      "/integrations/" + item.id + "/test",
                      {},
                    );
                    setNotice(result.message);
                  })
                }
              >
                <Play size={14} />
                Test local adapter
              </button>
            ) : (
              <span className="connection-note">
                No external connection configured
              </span>
            )}
          </section>
        ))}
      </div>
      <section className="panel fhir-import">
        <div className="panel-head">
          <div>
            <p className="eyebrow">FHIR R4 / SYNTHETIC SANDBOX</p>
            <h2>Import an evidence-backed claim bundle</h2>
            <p>
              Validated local mapping into intake, analysis and Claim Passport.
            </p>
          </div>
          <Badge status="DEMO_ADAPTER" />
        </div>
        <div className="fhir-body">
          <div className="supported-contract">
            <h3>Supported demo contract</h3>
            <p>
              Collection Bundle · one Patient, Coverage and active Claim ·
              Organization references · text/plain DocumentReference + Binary ·
              one LAP-APP-01 package · whole-rupee INR total.
            </p>
            <p>
              References must resolve inside the bundle. No remote fetch, NHCX
              transport, conformance certification or hospital connection is
              implemented.
            </p>
          </div>
          <div className="actions">
            <button
              disabled={busy}
              onClick={() =>
                perform(async () => {
                  setText(
                    JSON.stringify(
                      await api("/integrations/fhir/sample"),
                      null,
                      2,
                    ),
                  );
                })
              }
            >
              <FileJson size={16} />
              Load synthetic FHIR Bundle
            </button>
            <label className="button">
              Upload Bundle JSON
              <input
                type="file"
                accept=".json"
                hidden
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    if (file.size > 1500000) {
                      setError("Bundle JSON must be smaller than 1.5 MB.");
                      return;
                    }
                    setText(await file.text());
                  }
                  e.target.value = "";
                }}
              />
            </label>
            <button disabled={!text} onClick={saveSample}>
              <Download size={15} />
              Download sample
            </button>
          </div>
          <label className="bundle-label">
            Bundle JSON
            <textarea
              aria-label="FHIR Bundle JSON"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Load the provided synthetic bundle or paste JSON matching the supported contract."
              spellCheck={false}
            />
          </label>
          <button
            className="primary"
            disabled={!text || busy || !canWrite(role)}
            onClick={() =>
              perform(async () => {
                const bundle = JSON.parse(text);
                setJob(null);
                setJob(
                  await api<ImportResult>("/integrations/fhir/import", bundle),
                );
              })
            }
          >
            <Play size={16} />
            Import & analyse FHIR Bundle
          </button>
          {job && (
            <div className="fhir-result" role="status">
              <Badge status={job.status} />
              <h3>
                {job.claim_id} · {job.mapping.patient}
              </h3>
              <p>
                {job.mapping.provider} · {job.mapping.payer} · INR{" "}
                {job.mapping.amount.toLocaleString("en-IN")} ·{" "}
                {job.mapping.documents} evidence document(s)
              </p>
              <small>{job.adapter}</small>
              {job.status === "COMPLETED" && (
                <Link
                  className="button primary"
                  href={"/claims/" + job.claim_id}
                >
                  Open imported Claim Passport
                  <ArrowRight size={15} />
                </Link>
              )}
              {job.data.error && (
                <p className="error-banner">{job.data.error}</p>
              )}
              {job.status === "FAILED" && (
                <button
                  disabled={busy || !canWrite(role)}
                  onClick={() =>
                    perform(async () => {
                      const result = await api<AnalysisJob>(
                        "/analysis-jobs/" + job.id + "/retry",
                        {},
                      );
                      setJob({ ...job, ...result });
                    })
                  }
                >
                  Retry analysis
                </button>
              )}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
