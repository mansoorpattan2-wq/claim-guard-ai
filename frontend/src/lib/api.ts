export type Entry = {
  id: string;
  claim_id: string;
  status: string;
  title?: string;
  rule?: string;
  data: Record<string, any>;
};
export type Claim = {
  id: string;
  patient: string;
  hospital: string;
  procedure: string;
  amount: number;
  status: string;
  readiness: number;
  data: {
    payer: string;
    owner: string;
    admission: string;
    discharge: string;
    doctor: string;
    checks: Record<string, number>;
    weights: Record<string, number>;
    line_items: { description: string; category: string; amount: number }[];
    ground_truth: { category: string };
    [key: string]: any;
  };
  findings?: Entry[];
  documents?: {
    id: string;
    kind: string;
    title: string;
    text: string;
    hash: string;
    data: Record<string, any>;
  }[];
  tasks?: Entry[];
  runs?: { id: string; agent: string; data: Record<string, any> }[];
  decisions?: Entry[];
};
export type Event = {
  id: string;
  claim_id: string;
  timestamp: string;
  actor: string;
  event: string;
  data: Record<string, any>;
};
export const roles = [
  "Claims Executive",
  "Claims Manager",
  "Medical Reviewer",
  "Integrity Investigator",
  "Payer Reviewer",
  "Administrator",
  "Auditor",
];
export const canWrite = (r: string) =>
  ["Claims Executive", "Claims Manager"].includes(r);
export const canReview = (r: string) =>
  ["Claims Manager", "Medical Reviewer", "Payer Reviewer"].includes(r);
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const token =
    typeof window === "undefined" ? "" : sessionStorage.getItem("cg-token");
  const res = await fetch("/api" + path, {
    signal: AbortSignal.timeout(10000),
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer " + token } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  }).catch(() => {
    throw new Error(
      "The local API is unavailable. Start the backend, then retry. No successful check is assumed.",
    );
  });
  if (!res.ok) {
    if (res.status >= 500)
      throw new Error(
        "The local API could not complete this request. Retry or request manual review; no successful check is assumed.",
      );
    let message = "Request failed. Please retry.";
    try {
      const error = await res.json();
      message =
        typeof error.detail === "string"
          ? error.detail
          : JSON.stringify(error.detail);
    } catch {}
    throw new Error(message);
  }
  return res.json();
}
export async function establish(role: string) {
  const result = await api<{ token: string }>("/session", { role });
  sessionStorage.setItem("cg-token", result.token);
  sessionStorage.setItem("cg-role", role);
}

export async function apiText(path: string): Promise<string> {
  const res = await fetch("/api" + path, {
    headers: { Authorization: "Bearer " + sessionStorage.getItem("cg-token") },
  });
  if (!res.ok)
    throw new Error(
      "Passport export failed. Reconnect your demo session and retry.",
    );
  return res.text();
}
export function uploadFiles(
  path: string,
  files: File[],
  onProgress: (percent: number) => void,
): Promise<IntakePreview> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api" + path);
    xhr.setRequestHeader(
      "Authorization",
      "Bearer " + sessionStorage.getItem("cg-token"),
    );
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () =>
      reject(new Error("Upload connection failed. Please retry."));
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else
          reject(
            new Error(
              typeof body.detail === "string"
                ? body.detail
                : "Document upload failed.",
            ),
          );
      } catch {
        reject(new Error("Unexpected upload response. Please retry."));
      }
    };
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    xhr.send(form);
  });
}
export type IntakePreview = {
  id: string;
  status: string;
  claim_id: string | null;
  files: {
    id: string;
    kind: string;
    data: {
      filename: string;
      size: number;
      extraction_status: string;
      sha256: string;
    };
  }[];
  identity: Record<string, string>;
  conflicts: string[];
};
export type ExecutionStep = {
  agent: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  duration_ms?: number;
  inputs_summary?: string;
  tools?: string[];
  evidence_refs?: string[];
  finding_refs?: string[];
  next_transition?: string;
  error?: string;
  output?: Record<string, unknown>;
  job_id?: string;
};
export type AnalysisJob = {
  id: string;
  claim_id: string;
  status: string;
  data: {
    steps: ExecutionStep[];
    current_step: number;
    failed_step?: string;
    error?: string;
    started_at?: string;
    ended_at?: string;
  };
};
