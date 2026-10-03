"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, Claim, Entry, canReview } from "@/lib/api";
import { Badge } from "./ui";
import {
  ClipboardCheck,
  ArrowUpRight,
  AlertTriangle,
  CheckCircle2,
  Lock,
} from "lucide-react";
type ReviewItem = { claim: Claim; finding: Entry };
export default function ReviewWorkspace({
  role,
  onChanged,
}: {
  role: string;
  onChanged: () => Promise<void>;
}) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [decision, setDecision] = useState("AGREE");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const actionLock = useRef(false);
  async function load() {
    setLoading(true);
    try {
      setItems(await api<ReviewItem[]>("/review"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const item = items.find((x) => x.finding.id === selected) || items[0];
  async function record() {
    if (!item || actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<Claim>(
        "/review/" + item.finding.id + "/decision",
        { decision, reason },
      );
      setNotice(
        "Human disposition recorded. " +
          result.id +
          " is " +
          result.status.replaceAll("_", " ") +
          ". Original evidence retained.",
      );
      setReason("");
      await load();
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={16} />
          {error}
          <button onClick={load}>Retry</button>
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </div>
      )}
      <div className="review-layout">
        <section className="panel review-queue">
          <div className="panel-head">
            <h2>Review queue</h2>
            <span>{items.length} findings</span>
          </div>
          {loading ? (
            <p className="empty">Loading review findings…</p>
          ) : !items.length ? (
            <div className="empty">
              <ClipboardCheck />
              <p>No findings awaiting policy or medical review.</p>
            </div>
          ) : (
            items.map((x) => (
              <button
                key={x.finding.id}
                className={
                  "review-item " +
                  (item?.finding.id === x.finding.id ? "selected" : "")
                }
                onClick={() => {
                  setSelected(x.finding.id);
                  setReason("");
                }}
              >
                <div>
                  <strong>{x.claim.id}</strong>
                  <Badge status={x.finding.status} />
                </div>
                <h3>{x.finding.title}</h3>
                <p>
                  {x.claim.patient} · {x.claim.hospital}
                </p>
                <small>
                  {x.finding.rule} · {x.finding.data.agent} agent
                </small>
              </button>
            ))
          )}
        </section>
        {item && (
          <section className="panel review-detail">
            <div className="panel-head">
              <div>
                <p className="eyebrow">{item.claim.id} / HUMAN AUTHORITY</p>
                <h2>{item.finding.title}</h2>
              </div>
              <Link
                className="button"
                href={
                  "/claims/" + item.claim.id + "/evidence/" + item.finding.id
                }
              >
                Open evidence viewer
                <ArrowUpRight size={15} />
              </Link>
            </div>
            <div className="review-content">
              <p>{item.finding.data.description}</p>
              <div className="recommendation">
                <strong>Recommended next step</strong>
                <p>{item.finding.data.recommendation}</p>
              </div>
              {item.finding.data.evidence.map(
                (c: Record<string, string | number>) => (
                  <div className="citation-card" key={c.id}>
                    <p className="eyebrow">
                      {c.source} · v{c.version}
                    </p>
                    <h3>
                      {c.section} · {c.title}
                    </h3>
                    <blockquote>{c.text}</blockquote>
                    <small>
                      Page {c.page} · {c.authority} · {c.effective_date} →{" "}
                      {c.expiry_date}
                    </small>
                  </div>
                ),
              )}
              <h3>Record a human disposition</h3>
              <div className="disposition-options">
                {[
                  ["AGREE", "Agree"],
                  ["OVERRIDE", "Override"],
                  ["REQUEST_INFORMATION", "Request information"],
                  ["ESCALATE", "Escalate"],
                ].map(([value, title]) => (
                  <button
                    aria-pressed={decision === value}
                    className={decision === value ? "selected" : ""}
                    key={value}
                    onClick={() => setDecision(value)}
                  >
                    {title}
                  </button>
                ))}
              </div>
              <label className="review-reason">
                Review note{decision === "OVERRIDE" ? " — mandatory" : ""}
                <textarea
                  aria-label="Review reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain your interpretation. Existing claim records and sources are preserved."
                />
              </label>
              <p className="model-note">
                Agree confirms the concern. Override can clear an interpretive
                billing finding; policy validity and missing-evidence hard gates
                remain in force. Information requests are in-app records, not
                external messages.
              </p>
              <button
                className="primary"
                disabled={
                  busy ||
                  !canReview(role) ||
                  (decision === "OVERRIDE" && reason.trim().length < 3)
                }
                onClick={record}
              >
                Record disposition
              </button>
              {!canReview(role) && (
                <p className="permission">
                  <Lock size={14} />
                  Select Medical Reviewer, Payer Reviewer or Claims Manager to
                  make a decision.
                </p>
              )}
              <Link
                className="review-history-link"
                href={"/claims/" + item.claim.id}
              >
                View claim, prior decisions and audit
                <ArrowUpRight size={14} />
              </Link>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
