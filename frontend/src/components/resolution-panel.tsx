"use client";
import Link from "next/link";
import {
  CheckCircle2,
  ArrowRight,
  FileText,
  Lock,
  Send,
  Play,
  Upload,
  ShieldCheck,
  Activity,
} from "lucide-react";
import { Entry, Claim, canWrite, api } from "@/lib/api";
import { Badge } from "./ui";
export default function ResolutionPanel({
  task: t,
  claim: c,
  role,
  busy,
  step,
  action,
  onError: setError,
  onStep: setStep,
}: {
  task: Entry;
  claim: Claim;
  role: string;
  busy: boolean;
  step: string;
  action: (fn: () => Promise<unknown>, message?: string) => Promise<void>;
  onError: (message: string) => void;
  onStep: (message: string) => void;
}) {
  return (
    <section key={t.id} className="panel resolution-panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">
            {t.id} · {c.id}
          </p>
          <h2>Operative report missing</h2>
        </div>
        <Badge status={t.status} />
      </div>
      <p>
        The smallest corrective action: obtain the existing signed report from
        the hospital claims desk. Clinical content is never created by the
        resolution agent.
      </p>
      <div className="stepper">
        {["Request", "Send", "Receive", "Validate"].map((x, i) => (
          <div
            key={x}
            className={
              ["DRAFTED", "REQUESTED", "RECEIVED", "COMPLETED"].indexOf(
                t.status,
              ) >= i
                ? "done"
                : ""
            }
          >
            <span>{i + 1}</span>
            {x}
          </div>
        ))}
      </div>
      <div className="request-meta">
        <span>
          Required evidence<strong>Signed operative report</strong>
        </span>
        <span>
          Requested from<strong>Hospital Claims Desk</strong>
        </span>
        <span>
          Dependent checks<strong>Evidence · Clinical · Passport</strong>
        </span>
      </div>
      {t.data.request && (
        <div className="document-text request-text">{t.data.request}</div>
      )}
      {t.data.response && (
        <details open={t.status === "RECEIVED"}>
          <summary>Received document · inspect source</summary>
          <pre className="document-text">{t.data.response}</pre>
        </details>
      )}
      {t.status === "COMPLETED" && (
        <div className="success-banner">
          <CheckCircle2 />
          <div>
            <strong className="transition">
              {t.data.before}% → {t.data.after}%
            </strong>
            <p>Evidence validated. Passport updated. Audit recorded.</p>
          </div>
          <Link href={"/claims/" + c.id}>
            Open updated passport <ArrowRight size={15} />
          </Link>
        </div>
      )}
      {!canWrite(role) && (
        <p className="permission">
          <Lock size={14} /> Switch to Claims Executive or Claims Manager to
          resolve evidence.
        </p>
      )}
      <div className="actions">
        <button
          disabled={busy || !canWrite(role) || t.status === "COMPLETED"}
          onClick={() =>
            action(
              () =>
                api("/resolutions/" + t.id + "/request", {
                  action: "generate",
                }),
              "Request drafted. Review the text before simulating delivery.",
            )
          }
        >
          <FileText size={15} />
          Generate request
        </button>
        <button
          disabled={
            busy ||
            !canWrite(role) ||
            !["DRAFTED", "REQUESTED"].includes(t.status)
          }
          onClick={() =>
            action(
              () =>
                api("/resolutions/" + t.id + "/request", {
                  action: "simulate_send",
                }),
              "Request delivery simulated. No external message sent.",
            )
          }
        >
          <Send size={15} />
          Simulate request
        </button>
        <button
          disabled={busy || !canWrite(role) || t.status !== "REQUESTED"}
          onClick={() =>
            action(
              () => api("/resolutions/" + t.id + "/simulate-response", {}),
              "Synthetic operative report received. Inspect it before validation.",
            )
          }
        >
          <Play size={15} />
          Simulate response
        </button>
        <label
          className={
            "button " +
            (t.status !== "REQUESTED" && t.status !== "RECEIVED"
              ? "disabled"
              : "")
          }
        >
          <Upload size={15} />
          Upload text response
          <input
            hidden
            type="file"
            accept=".txt"
            disabled={
              busy ||
              !canWrite(role) ||
              !["REQUESTED", "RECEIVED"].includes(t.status)
            }
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                if (file.size > 100000) {
                  setError(
                    "Response must be a text document smaller than 100 KB.",
                  );
                  return;
                }
                const text = await file.text();
                await action(
                  () => api("/resolutions/" + t.id + "/response", { text }),
                  "Response received; validation is required.",
                );
              }
              e.target.value = "";
            }}
          />
        </label>
        <button
          className="primary"
          disabled={busy || !canWrite(role) || t.status !== "RECEIVED"}
          onClick={() =>
            action(async () => {
              setStep("Validating identity, procedure, date and signature");
              await api("/resolutions/" + t.id + "/complete", {});
            }, "Evidence validated. Only dependent checks reran.")
          }
        >
          <ShieldCheck size={16} />
          Validate & update passport
        </button>
      </div>
      {step && (
        <p className="running">
          <Activity size={15} />
          {step}
        </p>
      )}
    </section>
  );
}
