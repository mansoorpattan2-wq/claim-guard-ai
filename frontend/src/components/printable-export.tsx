"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiText } from "@/lib/api";
import { Printer, Download } from "lucide-react";
export default function PrintableExport({ claimId }: { claimId: string }) {
  const [html, setHtml] = useState("");
  const [error, setError] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);
  function load() {
    setError("");
    setHtml("");
    return apiText("/claims/" + claimId + "/printable")
      .then(setHtml)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    load();
  }, [claimId]);
  function save() {
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = claimId + "-readiness-passport.html";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="panel printable-panel">
      <div className="panel-head">
        <div>
          <h2>Claim Readiness Passport</h2>
          <p>
            Print or save as PDF using your browser. Standalone HTML preserves
            the source citations.
          </p>
        </div>
        <div className="actions">
          <Link className="button" href={"/claims/" + claimId}>
            Back to claim
          </Link>
          <button disabled={!html} onClick={save}>
            <Download size={15} />
            Download HTML
          </button>
          <button
            className="primary"
            disabled={!html}
            onClick={() => frame.current?.contentWindow?.print()}
          >
            <Printer size={15} />
            Print / Save PDF
          </button>
        </div>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button onClick={load}>Retry export</button>
        </div>
      )}
      {html ? (
        <iframe
          ref={frame}
          title={claimId + " printable evidence passport"}
          srcDoc={html}
          sandbox="allow-same-origin allow-modals"
        />
      ) : (
        !error && (
          <p className="empty">
            Generating source-grounded printable passport…
          </p>
        )
      )}
    </section>
  );
}
