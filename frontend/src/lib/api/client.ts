// Typed API client for the MedVault FastAPI backend.
import type {
  User,
  TokenResponse,
  DocumentResponse,
  PreviewResponse,
  RedactionRunRequest,
  JobResponse,
  RedactionReport,
  ExistingEntityFeedback,
  MissedFeedback,
  ModeComparisonRequest,
  ModeComparisonResponse,
  BatchResponse,
  AuditEntry,
  AuditVerification,
  PushSubscriptionRequest,
  PrivacyMode,
  ReviewQueue,
  ReviewDecision,
  ShareLink,
  ShareCreateRequest,
  JobInsight,
  WorkspaceAnalytics,
  PublicShare,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  status: number;
  body: unknown;
  fieldErrors: Array<{ path: string; message: string }>;
  constructor(
    status: number,
    message: string,
    body?: unknown,
    fieldErrors: Array<{ path: string; message: string }> = [],
  ) {
    super(message);
    this.status = status;
    this.body = body;
    this.fieldErrors = fieldErrors;
  }
}

function validationErrors(body: unknown): Array<{ path: string; message: string }> {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (!Array.isArray(detail)) return [];
  return detail.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return [];
    const item = entry as { loc?: unknown; msg?: unknown };
    if (typeof item.msg !== "string") return [];
    const path = Array.isArray(item.loc)
      ? item.loc
          .filter((part) => part !== "body")
          .map(String)
          .join(".")
      : "request";
    return [{ path: path || "request", message: item.msg }];
  });
}

type AuthGetter = () => string | null;
type OnUnauthorized = () => void;

let getToken: AuthGetter = () => null;
let onUnauthorized: OnUnauthorized = () => {};

export function configureApi(opts: { getToken: AuthGetter; onUnauthorized: OnUnauthorized }) {
  getToken = opts.getToken;
  onUnauthorized = opts.onUnauthorized;
}

async function parseError(res: Response): Promise<never> {
  let body: unknown = null;
  let msg = `Request failed (${res.status})`;
  try {
    const ct = res.headers.get("content-type") ?? "";
    if (ct.includes("application/json")) {
      body = await res.json();
      const d = (body as { detail?: unknown }).detail;
      if (typeof d === "string") msg = d;
      else if (
        Array.isArray(d) &&
        d.length &&
        typeof (d[0] as { msg?: unknown })?.msg === "string"
      ) {
        msg = (d[0] as { msg: string }).msg;
      }
    } else {
      msg = (await res.text()) || msg;
    }
  } catch {
    /* ignore parse errors */
  }
  if (res.status === 401) onUnauthorized();
  throw new ApiError(res.status, msg, body, validationErrors(body));
}

type ReqInit = Omit<RequestInit, "body"> & {
  body?: BodyInit | Record<string, unknown> | null;
  auth?: boolean;
};

async function request<T>(path: string, init: ReqInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const auth = init.auth ?? true;
  if (auth) {
    const t = getToken();
    if (t) headers.set("Authorization", `Bearer ${t}`);
  }
  let body: BodyInit | undefined;
  if (init.body != null) {
    if (
      init.body instanceof FormData ||
      init.body instanceof Blob ||
      typeof init.body === "string"
    ) {
      body = init.body;
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(init.body);
    }
  }
  const res = await fetch(`${API}${path}`, { ...init, headers, body });
  if (!res.ok) await parseError(res);
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

async function requestBlob(
  path: string,
): Promise<{ blob: Blob; filename: string | null; contentType: string }> {
  const headers = new Headers();
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetch(`${API}${path}`, { headers });
  if (!res.ok) await parseError(res);
  const cd = res.headers.get("content-disposition");
  const match = cd?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return {
    blob: await res.blob(),
    filename: match?.[1] ? decodeURIComponent(match[1]) : null,
    contentType: res.headers.get("content-type") ?? "application/octet-stream",
  };
}

// ---------- Auth ----------
export const authApi = {
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: { email, password }, auth: false }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  me: () => request<User>("/auth/me"),
  subscribePush: (sub: PushSubscriptionRequest) =>
    request<void>("/auth/push/subscribe", { method: "POST", body: sub }),
  unsubscribePush: () => request<void>("/auth/push/subscribe", { method: "DELETE" }),
};

// ---------- Documents ----------
export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const fd = new FormData();
    fd.append("file", file);
    return xhrUpload<DocumentResponse>("/documents/upload", fd, onProgress);
  },
  get: (documentId: string) => request<DocumentResponse>(`/documents/${documentId}`),
  preview: (documentId: string) => request<PreviewResponse>(`/documents/${documentId}/preview`),
  previewPage: (documentId: string, pageNumber: number) =>
    requestBlob(`/documents/${documentId}/preview/page/${pageNumber}`),
};

// ---------- Redaction ----------
export const redactionApi = {
  run: (req: RedactionRunRequest, idempotencyKey: string) =>
    request<JobResponse>("/redaction/run", {
      method: "POST",
      body: req as unknown as Record<string, unknown>,
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  status: (jobId: string) => request<JobResponse>(`/redaction/${jobId}/status`),
  report: (jobId: string) => request<RedactionReport>(`/redaction/${jobId}/report`),
  downloadReport: (jobId: string) => requestBlob(`/redaction/${jobId}/report/download`),
  heatmap: (jobId: string) => requestBlob(`/redaction/${jobId}/heatmap`),
  outputPreview: (jobId: string) => request<PreviewResponse>(`/redaction/${jobId}/preview`),
  outputPreviewPage: (jobId: string, pageNumber: number) =>
    requestBlob(`/redaction/${jobId}/preview/page/${pageNumber}`),
  feedback: (documentId: string, fb: ExistingEntityFeedback | MissedFeedback) =>
    request<{ feedback_id: string }>(`/redaction/${documentId}/feedback`, {
      method: "POST",
      body: fb as unknown as Record<string, unknown>,
    }),
  download: (jobId: string) => requestBlob(`/redaction/${jobId}/download`),
  compareModes: (req: ModeComparisonRequest) =>
    request<ModeComparisonResponse>("/redaction/compare-modes", {
      method: "POST",
      body: req as unknown as Record<string, unknown>,
    }),
};

// ---------- Batch ----------
export const batchApi = {
  upload: (
    files: File[],
    privacyMode: PrivacyMode,
    idempotencyKey: string,
    onProgress?: (pct: number) => void,
  ) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("privacy_mode", privacyMode);
    return xhrUpload<BatchResponse>("/batch/upload", fd, onProgress, {
      "Idempotency-Key": idempotencyKey,
    });
  },
  status: (batchJobId: string) => request<BatchResponse>(`/batch/${batchJobId}/status`),
  download: (batchJobId: string) => requestBlob(`/batch/${batchJobId}/download`),
};

// ---------- Audit ----------
export const auditApi = {
  trail: (documentId: string) => request<AuditEntry[]>(`/audit/${documentId}`),
  verify: (documentId: string) => request<AuditVerification>(`/audit/verify/${documentId}`),
};

// ---------- Human review ----------
export const reviewApi = {
  queue: (jobId: string) => request<ReviewQueue>(`/review/${jobId}`),
  confirmAll: (jobId: string) => request<ReviewQueue>(`/review/${jobId}/confirm-all`, { method: "POST" }),
  decide: (jobId: string, entityId: string, decision: ReviewDecision, note?: string | null) =>
    request(`/review/${jobId}/entities/${entityId}`, { method: "PUT", body: { decision, note } }),
  finalize: (jobId: string, approve: boolean, note?: string | null) =>
    request<ReviewQueue>(`/review/${jobId}/finalize`, { method: "POST", body: { approve, note } }),
};

// ---------- Controlled sharing ----------
export const sharingApi = {
  list: (jobId: string) => request<ShareLink[]>(`/shares/${jobId}`),
  create: (jobId: string, payload: ShareCreateRequest) =>
    request<ShareLink>(`/shares/${jobId}`, { method: "POST", body: payload }),
  revoke: (shareId: string) => request<ShareLink>(`/shares/${shareId}/revoke`, { method: "POST" }),
};

export const publicShareApi = {
  details: (token: string, password?: string) =>
    request<PublicShare>(`/shares/public/${token}`, { method: "POST", body: { password }, auth: false }),
  download: async (token: string, password?: string) => {
    const res = await fetch(`${API}/shares/public/${token}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) await parseError(res);
    const cd = res.headers.get("content-disposition");
    const match = cd?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    return { blob: await res.blob(), filename: match?.[1] ? decodeURIComponent(match[1]) : "medvault-redacted-document" };
  },
};

// ---------- Privacy-safe intelligence ----------
export const intelligenceApi = {
  job: (jobId: string) => request<JobInsight>(`/intelligence/jobs/${jobId}`),
  workspace: (jobIds: string[] = []) => {
    const query = jobIds.length ? `?${new URLSearchParams(jobIds.map((id) => ["job_id", id])).toString()}` : "";
    return request<WorkspaceAnalytics>(`/intelligence/workspace${query}`);
  },
};

// ---------- Health ----------
export const healthApi = {
  check: async () => {
    const res = await fetch(`${BASE}/health`);
    return res.ok;
  },
};

// XHR upload wrapper for progress events (fetch doesn't expose upload progress).
function xhrUpload<T>(
  path: string,
  fd: FormData,
  onProgress?: (pct: number) => void,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}${path}`);
    const t = getToken();
    if (t) xhr.setRequestHeader("Authorization", `Bearer ${t}`);
    Object.entries(extraHeaders).forEach(([name, value]) => xhr.setRequestHeader(name, value));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          resolve(xhr.responseText as unknown as T);
        }
      } else {
        if (xhr.status === 401) onUnauthorized();
        let msg = `Request failed (${xhr.status})`;
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
          const d = (body as { detail?: unknown }).detail;
          if (typeof d === "string") msg = d;
          else if (
            Array.isArray(d) &&
            d.length &&
            typeof (d[0] as { msg?: unknown })?.msg === "string"
          ) {
            msg = (d[0] as { msg: string }).msg;
          }
        } catch {
          /* ignore */
        }
        reject(new ApiError(xhr.status, msg, body, validationErrors(body)));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error"));
    xhr.send(fd);
  });
}

export function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
