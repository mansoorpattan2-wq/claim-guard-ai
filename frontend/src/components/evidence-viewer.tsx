"use client";
import { useState } from "react";
import Link from "next/link";
import { Lock, FileText } from "lucide-react";
import { Claim, Entry, canReview } from "@/lib/api";
import { label, Progress, Badge } from "./ui";
export default function Evidence({
  current,
  finding,
  role,
  busy,
  onDecision,
}: {
  current: Claim;
  finding: Entry;
  role: string;
  busy: boolean;
  onDecision: (decision: string, reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const citation = finding.data.evidence[0];
  if (!citation)
    return (
      <section className="panel later">
        <h2>Policy check unavailable — human review required.</h2>
        <p>
          No effective source supports this check. The finding cannot be marked
          as passed.
        </p>
        <Link className="button" href={"/claims/" + current.id}>
          Return to passport
        </Link>
      </section>
    );
  return (
    <>
      <Link className="back-link" href={"/claims/" + current.id}>
        ← Back to {current.id} passport
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">EVIDENCE VIEWER / {finding.rule}</p>
          <h1>Verify the finding. Inspect the source.</h1>
          <p>Inspect the source behind this finding.</p>
        </div>
        <Badge status={finding.status} />
      </div>
      <div className="evidence-layout">
        <section className="panel finding-detail">
          <span className="severity">{finding.data.severity}</span>
          <h2>{finding.title}</h2>
          <p>{finding.data.description}</p>
          <dl>
            <dt>Originating agent</dt>
            <dd>{label(finding.data.agent)} · v1.0</dd>
            <dt>Triggered rule</dt>
            <dd>{finding.rule}</dd>
            <dt>Recommended next step</dt>
            <dd>{finding.data.recommendation}</dd>
          </dl>
          <h3>Confidence dimensions</h3>
          {Object.entries(
            finding.data.confidence as Record<string, number>,
          ).map(([key, val]) => (
            <div className="confidence" key={key}>
              <span>{label(key)}</span>
              <Progress value={Math.round(val * 100)} />
            </div>
          ))}
          <p className="model-note">
            Confidence reflects this controlled synthetic scenario, not
            calibrated production accuracy.
          </p>
          <div className="human-controls">
            <h3>Human disposition</h3>
            <label>
              Reason or review note
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain your assessment. Original evidence is preserved."
              />
            </label>
            <div className="actions">
              {[
                ["AGREE", "Agree"],
                ["INCORRECT", "Incorrect finding"],
                ["SPECIALIST", "Specialist review"],
              ].map(([value, name]) => (
                <button
                  key={value}
                  disabled={
                    busy || !canReview(role) || reason.trim().length < 3
                  }
                  onClick={() => onDecision(value, reason.trim())}
                >
                  {name}
                </button>
              ))}
            </div>
            {!canReview(role) && (
              <p className="permission">
                <Lock size={14} />
                Select Medical Reviewer, Payer Reviewer or Claims Manager to
                record a decision.
              </p>
            )}
          </div>
        </section>
        <section className="panel source-viewer">
          <div className="source-toolbar">
            <FileText size={18} />
            <span>{citation.source}</span>
            <b>Page {citation.page}</b>
          </div>
          <div className="paper">
            <div className="synthetic-stamp">
              SYNTHETIC POLICY — DEMONSTRATION ONLY
            </div>
            <p className="eyebrow">DEMOCARE HEALTH INSURANCE</p>
            <h2>Health Insurance Policy 2026</h2>
            <div className="paper-rule" />
            <p>Version {citation.version} · Effective 01 January 2026</p>
            <h3>
              {citation.section} · {citation.title}
            </h3>
            <mark>{citation.text}</mark>
            <p className="paper-note">
              This synthetic source exists solely to demonstrate grounded claim
              readiness checks. It does not represent real insurer coverage or
              medical advice.
            </p>
            <div className="paper-footer">
              DemoCare · Policy v{citation.version}
              <span>{citation.page}</span>
            </div>
          </div>
          <div className="source-metadata">
            <div>
              Authority<strong>{citation.authority}</strong>
            </div>
            <div>
              Source version<strong>{citation.version}</strong>
            </div>
            <div>
              Chunk ID<strong>{citation.id}</strong>
            </div>
            <div>
              Validity
              <strong>
                {citation.effective_date} → {citation.expiry_date}
              </strong>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
