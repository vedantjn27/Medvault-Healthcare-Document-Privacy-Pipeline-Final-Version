import { createFileRoute, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { auditApi } from "@/lib/api/client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/error-banner";
import { ShieldCheck, ShieldAlert, ShieldQuestion, Hash, Search } from "lucide-react";
import { fmtDate } from "@/lib/format";
import { z } from "zod";
import { toast } from "sonner";

export const Route = createFileRoute("/app/audit")({
  validateSearch: z.object({ documentId: z.string().optional() }),
  component: AuditPage,
  head: () => ({ meta: [{ title: "Audit Trail — MedVault" }] }),
});

function AuditPage() {
  const { documentId: initial } = useSearch({ from: "/app/audit" });
  const [documentId, setDocumentId] = useState(initial ?? "");
  const [active, setActive] = useState(initial ?? "");
  const trail = useQuery({
    queryKey: ["audit", active],
    queryFn: () => auditApi.trail(active),
    enabled: !!active,
  });
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [verify, setVerify] = useState<import("@/lib/api/types").AuditVerification | null>(null);
  const [verifyErr, setVerifyErr] = useState<unknown>(null);

  async function runVerify() {
    if (!active) return;
    setVerifyBusy(true);
    setVerifyErr(null);
    try {
      const r = await auditApi.verify(active);
      setVerify(r);
      if (r.valid) toast.success(`Chain valid — ${r.entries_checked} entries verified.`);
      else toast.error(`Integrity broken at entry ${r.broken_entry_id ?? "unknown"}.`);
    } catch (e) {
      setVerifyErr(e);
    } finally {
      setVerifyBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Audit trail</h1>
        <p className="mt-1 text-muted-foreground">
          Hash-linked events for every action performed on a document.
        </p>
      </div>

      <Card className="p-6">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
          <div>
            <Label>Document ID</Label>
            <Input
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="Paste a document ID"
              className="font-mono text-xs"
            />
          </div>
          <div className="flex items-end">
            <Button
              className="gap-2"
              onClick={() => {
                setVerify(null);
                setVerifyErr(null);
                setActive(documentId);
              }}
              disabled={!documentId}
            >
              <Search className="h-4 w-4" /> Load trail
            </Button>
          </div>
          <div className="flex items-end">
            <Button
              variant="outline"
              className="gap-2"
              onClick={runVerify}
              disabled={!active || verifyBusy}
            >
              <ShieldCheck className="h-4 w-4" /> {verifyBusy ? "Verifying…" : "Verify integrity"}
            </Button>
          </div>
        </div>

        {verify ? (
          <div
            className={`mt-4 flex items-start gap-3 rounded-lg border p-4 ${verify.valid ? "border-success/40 bg-success/5" : "border-destructive/40 bg-destructive/5"}`}
          >
            {verify.valid ? (
              <ShieldCheck className="h-5 w-5 text-success" />
            ) : (
              <ShieldAlert className="h-5 w-5 text-destructive" />
            )}
            <div>
              <p className="font-semibold">{verify.valid ? "Chain valid" : "Integrity broken"}</p>
              <p className="text-xs text-muted-foreground">
                {verify.entries_checked} entries checked
                {verify.broken_entry_id ? ` — first mismatch at ${verify.broken_entry_id}` : ""}
              </p>
            </div>
          </div>
        ) : null}
        {verifyErr ? (
          <div className="mt-4">
            <ErrorBanner error={verifyErr} />
          </div>
        ) : null}
      </Card>

      {trail.error ? <ErrorBanner error={trail.error} /> : null}
      {trail.isLoading ? <Skeleton className="h-64" /> : null}

      {trail.data ? (
        <Card className="p-6">
          <h2 className="mb-4 font-display font-semibold">Events ({trail.data.length})</h2>
          {trail.data.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events recorded for this document.</p>
          ) : (
            <ol className="relative space-y-4 border-l-2 border-border pl-6">
              {trail.data
                .slice()
                .sort((a, b) => a.sequence - b.sequence)
                .map((entry) => (
                  <li key={entry.id} className="relative">
                    <div className="absolute -left-[31px] top-1 grid h-5 w-5 place-items-center rounded-full bg-primary text-primary-foreground">
                      <Hash className="h-2.5 w-2.5" />
                    </div>
                    <div className="rounded-lg border bg-card p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="font-mono text-[10px]">
                          #{entry.sequence}
                        </Badge>
                        <span className="font-semibold text-sm">{entry.event_type}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {fmtDate(entry.created_at)}
                        </span>
                        {entry.job_id ? (
                          <Badge variant="secondary" className="text-[10px]">
                            Job {entry.job_id.slice(-6)}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                        <KVBlock label="Hash" value={entry.entry_hash} mono />
                        <KVBlock label="Prev" value={entry.previous_hash ?? "—"} mono />
                      </div>
                      {Object.keys(entry.event_data ?? {}).length ? (
                        <details className="mt-2">
                          <summary className="cursor-pointer text-xs text-muted-foreground">
                            Event data
                          </summary>
                          <dl className="mt-2 grid gap-2 rounded bg-muted/50 p-3 text-xs sm:grid-cols-2">
                            {Object.entries(entry.event_data).map(([key, value]) => (
                              <div key={key} className="min-w-0">
                                <dt className="font-medium text-muted-foreground">{key}</dt>
                                <dd className="mt-0.5 break-words font-mono text-[11px]">
                                  {formatEventValue(value)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      ) : null}
                    </div>
                  </li>
                ))}
            </ol>
          )}
        </Card>
      ) : !active ? (
        <Card className="border-dashed p-10 text-center">
          <ShieldQuestion className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Load a document ID to view its append-only audit chain.
          </p>
        </Card>
      ) : null}
    </div>
  );
}

function formatEventValue(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "[unrenderable value]";
  }
}

function KVBlock({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded bg-muted/40 p-2">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className={`truncate ${mono ? "font-mono" : ""} text-[11px]`} title={value}>
        {value}
      </div>
    </div>
  );
}
