import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { documentsApi, redactionApi, triggerDownload } from "@/lib/api/client";
import { intelligenceApi, reviewApi, sharingApi } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import type {
  EntityReport,
  ExistingEntityFeedback,
  FileType,
  MissedFeedback,
} from "@/lib/api/types";
import { ENTITY_TYPES, PRIVACY_MODE_LABELS } from "@/lib/api/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ErrorBanner } from "@/components/error-banner";
import { DocumentPreview } from "@/components/document-preview";
import { CapsuleLoader } from "@/components/capsule-loader";
import { StatusBadge } from "@/routes/app.index";
import { pct } from "@/lib/format";
import {
  Download,
  ThumbsUp,
  ThumbsDown,
  Flag,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Gavel,
  ShieldOff,
  TrendingUp,
  ClipboardCheck,
  Share2,
  BrainCircuit,
  Check,
  FlagTriangleRight,
  Copy,
  Ban,
} from "lucide-react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
} from "recharts";

export const Route = createFileRoute("/app/jobs/$jobId")({
  component: JobPage,
});

function JobPage() {
  const { jobId } = Route.useParams();
  const qc = useQueryClient();

  const statusQ = useQuery({
    queryKey: ["job", jobId, "status"],
    queryFn: () => redactionApi.status(jobId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      const online = typeof navigator === "undefined" || navigator.onLine;
      return online && (s === "queued" || s === "processing") ? 2000 : false;
    },
  });
  const job = statusQ.data;
  const terminal = job && ["complete", "qa_failed", "error"].includes(job.status);
  const [completionRevealed, setCompletionRevealed] = useState(false);
  const showCompletionCapsule = job?.status === "complete" && !completionRevealed;
  const showProcessingState = !terminal || showCompletionCapsule;
  const showTerminalState = !!terminal && !showCompletionCapsule;

  useEffect(() => {
    if (job?.status !== "complete") {
      setCompletionRevealed(false);
      return;
    }
    const timer = window.setTimeout(() => setCompletionRevealed(true), 760);
    return () => window.clearTimeout(timer);
  }, [job?.status]);

  useEffect(() => {
    if (job)
      activityStore.update("job", jobId, { status: job.status, privacyMode: job.privacy_mode });
  }, [job, jobId]);

  useEffect(() => {
    if (terminal) {
      void qc.invalidateQueries({ queryKey: ["intelligence", jobId] });
      void qc.invalidateQueries({ queryKey: ["workspace-intelligence"] });
    }
  }, [terminal, qc, jobId]);

  const reportQ = useQuery({
    queryKey: ["job", jobId, "report"],
    queryFn: () => redactionApi.report(jobId),
    enabled: !!terminal && job?.status !== "error",
  });
  const originalPreviewQ = useQuery({
    queryKey: ["preview", job?.document_id],
    queryFn: () => documentsApi.preview(job!.document_id),
    enabled: !!terminal && job?.status !== "error" && !!job?.document_id,
    retry: 1,
  });
  const outputPreviewQ = useQuery({
    queryKey: ["job", jobId, "output-preview"],
    queryFn: () => redactionApi.outputPreview(jobId),
    enabled: !!terminal && job?.status !== "error",
    retry: 1,
  });

  // Heatmap blob URL
  const [heatmapUrl, setHeatmapUrl] = useState<string | null>(null);
  const [heatmapErr, setHeatmapErr] = useState<unknown>(null);
  useEffect(() => {
    let url: string | null = null;
    if (terminal && job?.status !== "error") {
      redactionApi
        .heatmap(jobId)
        .then(({ blob }) => {
          url = URL.createObjectURL(blob);
          setHeatmapUrl(url);
        })
        .catch((e) => setHeatmapErr(e));
    }
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [jobId, terminal, job?.status]);

  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState<unknown>(null);
  async function doDownload() {
    if (!job) return;
    setDownloading(true);
    setDownloadErr(null);
    try {
      const { blob, filename } = await redactionApi.download(jobId);
      const fileType = outputPreviewQ.data?.file_type ?? originalPreviewQ.data?.file_type;
      triggerDownload(blob, filename ?? `redacted-${jobId}.${fileExtension(fileType)}`);
      activityStore.update("job", jobId, { downloaded: true });
      activityStore.update("document", job.document_id, { downloaded: true });
      toast.success("Downloaded. You can download another copy during this session.");
      qc.invalidateQueries({ queryKey: ["job", jobId] });
    } catch (e) {
      setDownloadErr(e);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs text-muted-foreground">Redaction job</p>
          <h1 className="font-display text-2xl font-bold sm:text-3xl">
            {job ? PRIVACY_MODE_LABELS[job.privacy_mode] : "Loading…"}
          </h1>
          <div
            className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
            aria-live="polite"
            aria-atomic="true"
          >
            {job ? <StatusBadge status={job.status} /> : null}
            {job?.qa_passed ? (
              <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                <CheckCircle2 className="mr-1 h-3 w-3" /> QA passed
              </Badge>
            ) : null}
            {job?.reidentification_risk ? <RiskBadge risk={job.reidentification_risk} /> : null}
            <span className="font-mono text-[10px]">{jobId}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {job?.document_id ? (
            <Link to="/app/documents/$documentId" params={{ documentId: job.document_id }}>
              <Button variant="outline" size="sm">
                Back to document
              </Button>
            </Link>
          ) : null}
          {job?.status === "complete" ? (
            <Button className="gap-2 shadow-glow" onClick={doDownload} disabled={downloading}>
              <Download className="h-4 w-4" />
              {downloading ? "Preparing download…" : "Download copy"}
            </Button>
          ) : null}
        </div>
      </div>

      {statusQ.error ? <ErrorBanner error={statusQ.error} /> : null}
      {downloadErr ? <ErrorBanner error={downloadErr} title="Download failed" /> : null}

      {/* Progress or terminal state */}
      {showProcessingState ? (
        <Card className="p-6" aria-live="polite" aria-atomic="true">
          <div className="flex items-center gap-3">
            <CapsuleLoader
              className="capsule-loader-job shrink-0"
              tone="red"
              complete={showCompletionCapsule}
              label=""
            />
            <div className="flex-1">
              <p className="font-medium">Job is {job?.status ?? "queued"}…</p>
              <p className="text-xs text-muted-foreground">
                Polling every ~2s. This runs OCR, entity detection and QA.
              </p>
            </div>
          </div>
          {!showCompletionCapsule ? (
            <Progress value={job?.status === "processing" ? 60 : 25} className="mt-4" />
          ) : null}
        </Card>
      ) : null}

      {showTerminalState && job?.status === "error" ? (
        <Card className="border-destructive/40 bg-destructive/5 p-6">
          <div className="flex items-start gap-3">
            <ShieldOff className="h-5 w-5 text-destructive" />
            <div>
              <p className="font-semibold text-destructive">Processing failed</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {job.error_message ?? "Unknown error."}
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      {showTerminalState && job?.status === "qa_failed" ? (
        <Card className="border-warning/40 bg-warning/5 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-warning-foreground" />
            <div>
              <p className="font-semibold">QA failed — residual sensitive data detected</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Report and heatmap are available for review. Download is intentionally disabled,
                with no override.
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      {showTerminalState && job?.status !== "error" ? (
        <Tabs defaultValue="preview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="preview">Before / after</TabsTrigger>
            <TabsTrigger value="report">Report</TabsTrigger>
            <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
            <TabsTrigger value="review">Review queue</TabsTrigger>
            <TabsTrigger value="share">Secure share</TabsTrigger>
            <TabsTrigger value="insights">Intelligence</TabsTrigger>
            <TabsTrigger value="missed">Missed feedback</TabsTrigger>
            {job.reidentification_factors?.length ? (
              <TabsTrigger value="risk">Risk analysis</TabsTrigger>
            ) : null}
          </TabsList>
          <TabsContent value="preview">
            <div className="grid gap-4 xl:grid-cols-2">
              <Card className="min-w-0 p-4">
                <div className="mb-4">
                  <Badge variant="outline" className="border-warning/40 bg-warning/10">
                    Original — sensitive
                  </Badge>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Authenticated pre-redaction preview. Do not share or capture this panel.
                  </p>
                </div>
                {originalPreviewQ.isLoading ? (
                  <PreviewLoading label="Loading original document preview…" />
                ) : originalPreviewQ.error ? (
                  <ErrorBanner
                    error={originalPreviewQ.error}
                    title="Original preview unavailable"
                  />
                ) : originalPreviewQ.data ? (
                  <DocumentPreview
                    data={originalPreviewQ.data}
                    label="Original"
                    loadPage={(pageNumber) => documentsApi.previewPage(job.document_id, pageNumber)}
                  />
                ) : null}
              </Card>
              <Card className="min-w-0 border-success/30 p-4">
                <div className="mb-4">
                  <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                    Redacted output — actual generated file
                  </Badge>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Review this parsed output before downloading. It is not a simulated overlay.
                  </p>
                </div>
                {outputPreviewQ.isLoading ? (
                  <PreviewLoading label="Loading redacted output preview…" />
                ) : outputPreviewQ.error ? (
                  <ErrorBanner error={outputPreviewQ.error} title="Redacted preview unavailable" />
                ) : outputPreviewQ.data ? (
                  <DocumentPreview
                    data={outputPreviewQ.data}
                    label="Redacted"
                    loadPage={(pageNumber) => redactionApi.outputPreviewPage(jobId, pageNumber)}
                  />
                ) : null}
              </Card>
            </div>
            {job.status === "qa_failed" ? (
              <p className="mt-3 rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
                QA detected possible residual sensitive data. Use this preview for review only;
                downloading remains blocked.
              </p>
            ) : null}
          </TabsContent>
          <TabsContent value="report">
            {reportQ.isLoading ? (
              <div role="status" aria-live="polite">
                <p className="mb-2 text-sm text-muted-foreground">Loading redaction report…</p>
                <Skeleton className="h-64" />
              </div>
            ) : reportQ.error ? (
              <ErrorBanner error={reportQ.error} />
            ) : reportQ.data ? (
              <ReportPanel
                report={reportQ.data}
                jobId={jobId}
                onFeedbackSent={() => qc.invalidateQueries({ queryKey: ["job", jobId, "report"] })}
              />
            ) : null}
          </TabsContent>
          <TabsContent value="heatmap">
            <Card className="p-4">
              <h3 className="mb-2 font-display font-semibold">Redaction location map</h3>
              <p className="mb-4 text-xs text-muted-foreground">
                A privacy-safe page map: each coloured block marks a redacted location. Yellow is
                lower confidence, orange is medium, and red is high confidence. Use Before / after
                to inspect the generated document at readable size.
              </p>
              <HeatmapSummary entities={reportQ.data?.entities ?? []} />
              {heatmapErr ? (
                <ErrorBanner error={heatmapErr} />
              ) : heatmapUrl ? (
                <div className="overflow-auto rounded-lg border bg-slate-100 p-3">
                  <img
                    src={heatmapUrl}
                    alt="Page-aware map showing redacted locations and confidence"
                    className="mx-auto h-auto w-full max-w-[900px]"
                  />
                </div>
              ) : (
                <div role="status" aria-live="polite">
                  <p className="mb-2 text-sm text-muted-foreground">Loading SVG heatmap…</p>
                  <Skeleton className="h-96 w-full" />
                </div>
              )}
            </Card>
          </TabsContent>
          <TabsContent value="review">
            <ReviewPanel jobId={jobId} onChanged={() => qc.invalidateQueries({ queryKey: ["job", jobId, "report"] })} />
          </TabsContent>
          <TabsContent value="share">
            <SharePanel jobId={jobId} />
          </TabsContent>
          <TabsContent value="insights">
            <IntelligencePanel jobId={jobId} />
          </TabsContent>
          <TabsContent value="missed">
            <MissedFeedbackForm
              jobId={jobId}
              documentId={job.document_id}
              onSent={() => qc.invalidateQueries({ queryKey: ["job", jobId, "report"] })}
            />
          </TabsContent>
          {job.reidentification_factors?.length ? (
            <TabsContent value="risk">
              <Card className="p-6">
                <div className="mb-4 flex items-center gap-3">
                  <TrendingUp className="h-5 w-5 text-primary" />
                  <h3 className="font-display font-semibold">Re-identification risk analysis</h3>
                </div>
                <RiskBadge risk={job.reidentification_risk ?? "low"} large />
                <div className="mt-6">
                  <p className="text-sm font-medium">Safe factors considered:</p>
                  <ul className="mt-2 space-y-1.5">
                    {job.reidentification_factors.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> {f}
                      </li>
                    ))}
                  </ul>
                </div>
              </Card>
            </TabsContent>
          ) : null}
        </Tabs>
      ) : null}
    </div>
  );
}

function ReviewPanel({ jobId, onChanged }: { jobId: string; onChanged: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const queueQ = useQuery({ queryKey: ["review", jobId], queryFn: () => reviewApi.queue(jobId) });
  const decision = useMutation({
    mutationFn: ({ entityId, value }: { entityId: string; value: "confirmed" | "flagged" }) => reviewApi.decide(jobId, entityId, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review", jobId] }),
  });
  const confirmAll = useMutation({
    mutationFn: () => reviewApi.confirmAll(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review", jobId] }),
  });
  const finalize = useMutation({
    mutationFn: (approve: boolean) => reviewApi.finalize(jobId, approve, note || null),
    onSuccess: (_, approve) => {
      qc.invalidateQueries({ queryKey: ["review", jobId] });
      qc.invalidateQueries({ queryKey: ["workspace-intelligence"] });
      onChanged();
      toast.success(approve ? "Review approved. Secure sharing is now available." : "Changes requested. Sharing remains locked until this review is approved.");
    },
  });
  if (queueQ.isLoading) return <PreviewLoading label="Building human review queue…" />;
  if (queueQ.error || !queueQ.data) return <ErrorBanner error={queueQ.error ?? new Error("Review queue unavailable")} />;
  const queue = queueQ.data;
  return (
    <div className="space-y-4">
      <Card className="overflow-hidden border-primary/30 bg-primary/5 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 font-display text-lg font-semibold"><ClipboardCheck className="h-5 w-5 text-primary" /> Human review gate</div>
            <p className="mt-1 text-sm text-muted-foreground">Confirm each privacy-safe finding before allowing controlled distribution.</p>
          </div>
          <div className="flex items-center gap-2"><Badge variant="outline" className="border-primary/40 bg-primary/10">{queue.status.replace("_", " ")}</Badge><Button size="sm" disabled={confirmAll.isPending || queue.pending_count === 0 || queue.status === "approved"} onClick={() => confirmAll.mutate()}><Check className="mr-1.5 h-3.5 w-3.5" /> Confirm all</Button></div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <SummaryStat label="Findings" value={queue.entities.length} accent="chart-1" />
          <SummaryStat label="Awaiting review" value={queue.pending_count} accent="chart-4" />
          <SummaryStat label="Flagged" value={queue.flagged_count} accent="chart-5" />
        </div>
      </Card>
      {queue.status === "changes_requested" ? <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm"><p className="font-semibold text-warning">Changes requested — controlled sharing is locked.</p><p className="mt-1 text-muted-foreground">Resolve flagged findings or re-run the document as needed, then approve the completed review.</p></div> : null}
      <div className="grid gap-3">
        {queue.entities.map((entity) => (
          <Card key={entity.id} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2"><Badge variant="secondary">{entity.entity_type}</Badge><span className="text-xs text-muted-foreground">{Math.round(entity.confidence * 100)}% confidence · Page {entity.page_number ?? "—"}</span></div>
                <p className="mt-2 text-sm text-muted-foreground">{entity.explanation_text}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant={entity.review_decision === "confirmed" ? "default" : "outline"} disabled={decision.isPending || queue.status === "approved"} onClick={() => decision.mutate({ entityId: entity.id, value: "confirmed" })}><Check className="mr-1 h-3.5 w-3.5" /> Confirm</Button>
                <Button size="sm" variant={entity.review_decision === "flagged" ? "destructive" : "outline"} disabled={decision.isPending || queue.status === "approved"} onClick={() => decision.mutate({ entityId: entity.id, value: "flagged" })}><FlagTriangleRight className="mr-1 h-3.5 w-3.5" /> Flag</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Card className="p-4">
        <Label htmlFor="review-note">Review note (optional)</Label>
        <Textarea id="review-note" className="mt-2" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Record the decision rationale without adding raw PHI." />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button disabled={finalize.isPending} onClick={() => finalize.mutate(true)}><Check className="mr-2 h-4 w-4" /> Approve output</Button>
          <Button variant="outline" disabled={finalize.isPending} onClick={() => finalize.mutate(false)}>Request changes</Button>
        </div>
        {finalize.error ? <div className="mt-3"><ErrorBanner error={finalize.error} /></div> : null}
      </Card>
    </div>
  );
}

function SharePanel({ jobId }: { jobId: string }) {
  const qc = useQueryClient();
  const [password, setPassword] = useState("");
  const [hours, setHours] = useState("24");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [maxAccesses, setMaxAccesses] = useState("");
  const [role, setRole] = useState<"reviewer" | "recipient">("recipient");
  const linksQ = useQuery({ queryKey: ["shares", jobId], queryFn: () => sharingApi.list(jobId) });
  const create = useMutation({
    mutationFn: () => sharingApi.create(jobId, { role, expires_in_hours: Number(hours), password: password || null, recipient_email: recipientEmail || null, max_accesses: maxAccesses ? Number(maxAccesses) : null, allow_download: role === "recipient" }),
    onSuccess: async (link) => {
      qc.invalidateQueries({ queryKey: ["shares", jobId] });
      if (link.share_url) {
        try {
          await navigator.clipboard.writeText(`${window.location.origin}${link.share_url}`);
          toast.success("Secure share link created and copied to your clipboard");
        } catch {
          toast.success("Secure share link created. Open it from this browser to copy its address.");
        }
      }
      setPassword("");
      setRecipientEmail("");
      setMaxAccesses("");
    },
  });
  const revoke = useMutation({ mutationFn: (shareId: string) => sharingApi.revoke(shareId), onSuccess: () => qc.invalidateQueries({ queryKey: ["shares", jobId] }) });
  return <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
    <Card className="border-primary/30 p-5">
      <div className="flex items-center gap-2 font-display text-lg font-semibold"><Share2 className="h-5 w-5 text-primary" /> Controlled distribution</div>
      <p className="mt-2 text-sm text-muted-foreground">Links expire automatically, are revocable, and are only available after QA and review approval.</p>
      <div className="mt-5 space-y-3">
        <div><Label>Recipient role</Label><Select value={role} onValueChange={(value) => setRole(value as "reviewer" | "recipient")}><SelectTrigger className="mt-1"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="recipient">Recipient — download allowed</SelectItem><SelectItem value="reviewer">Reviewer — view only</SelectItem></SelectContent></Select></div>
        <div><Label>Expiry (hours)</Label><Input className="mt-1" inputMode="numeric" value={hours} onChange={(event) => setHours(event.target.value.replace(/\D/g, ""))} /></div>
        <div><Label>Recipient email (optional)</Label><Input className="mt-1" type="email" value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} placeholder="reviewer@organisation.com" /></div>
        <div><Label>Optional share password</Label><Input className="mt-1" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 10 characters" /></div>
        <div><Label>Maximum downloads (optional)</Label><Input className="mt-1" inputMode="numeric" value={maxAccesses} onChange={(event) => setMaxAccesses(event.target.value.replace(/\D/g, ""))} placeholder="Unlimited" /></div>
        <Button className="w-full" disabled={create.isPending || !Number(hours)} onClick={() => create.mutate()}><Copy className="mr-2 h-4 w-4" /> Create & copy link</Button>
        {create.error ? <ErrorBanner error={create.error} /> : null}
      </div>
    </Card>
    <Card className="p-5">
      <h3 className="font-display text-lg font-semibold">Active share links</h3>
      <div className="mt-4 space-y-3">{linksQ.isLoading ? <PreviewLoading label="Loading share controls…" /> : linksQ.data?.length ? linksQ.data.map((link) => <div key={link.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"><div><div className="flex items-center gap-2"><Badge variant="outline">{link.role}</Badge>{link.revoked_at ? <Badge variant="destructive">Revoked</Badge> : <Badge variant="secondary">Active</Badge>}</div><p className="mt-1 text-xs text-muted-foreground">Expires {new Date(link.expires_at).toLocaleString()} · {link.access_count}{link.max_accesses ? `/${link.max_accesses}` : ""} accesses</p></div>{!link.revoked_at ? <Button size="sm" variant="outline" disabled={revoke.isPending} onClick={() => revoke.mutate(link.id)}><Ban className="mr-1 h-3.5 w-3.5" /> Revoke</Button> : null}</div>) : <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No share links yet.</p>}</div>
    </Card>
  </div>;
}

function IntelligencePanel({ jobId }: { jobId: string }) {
  const insightQ = useQuery({ queryKey: ["intelligence", jobId], queryFn: () => intelligenceApi.job(jobId) });
  if (insightQ.isLoading) return <PreviewLoading label="Calculating privacy-safe intelligence…" />;
  if (insightQ.error || !insightQ.data) return <ErrorBanner error={insightQ.error ?? new Error("Intelligence unavailable")} />;
  const insight = insightQ.data;
  return <div className="space-y-5"><Card className="overflow-hidden border-primary/30 p-6"><div className="flex items-start gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl gradient-hero text-white"><BrainCircuit className="h-5 w-5" /></div><div><h3 className="font-display text-xl font-semibold">Privacy intelligence</h3><p className="mt-1 text-sm text-muted-foreground">Derived only from safe metadata, categories, confidence and QA results — never source values.</p></div></div><div className="mt-5 grid gap-3 sm:grid-cols-4"><SummaryStat label="Coverage" value={`${insight.coverage_percent}%`} accent="chart-2" /><SummaryStat label="Findings" value={insight.entity_count} accent="chart-1" /><SummaryStat label="Redacted" value={insight.redacted_count} accent="chart-3" /><SummaryStat label="Risk" value={insight.risk_level.replace("_", " ")} accent="chart-4" /></div></Card><div className="grid gap-5 lg:grid-cols-2"><Card className="p-5"><h3 className="font-display font-semibold">Category profile</h3><div className="mt-4 space-y-3">{Object.entries(insight.category_counts).sort((a,b) => b[1]-a[1]).map(([category,count]) => <div key={category}><div className="mb-1 flex justify-between text-xs"><span>{category}</span><span>{count}</span></div><Progress value={(count / Math.max(1, insight.redacted_count)) * 100} /></div>) || <p className="text-sm text-muted-foreground">No redacted categories.</p>}</div></Card><Card className="p-5"><h3 className="font-display font-semibold">Recommended next steps</h3><ul className="mt-4 space-y-3">{insight.recommendations.map((recommendation) => <li key={recommendation} className="flex gap-2 text-sm text-muted-foreground"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{recommendation}</li>)}</ul></Card></div></div>;
}

function PreviewLoading({ label }: { label: string }) {
  return (
    <div className="grid min-h-72 place-items-center rounded-xl border border-dashed bg-muted/20">
      <CapsuleLoader label={label} />
    </div>
  );
}

function HeatmapSummary({ entities }: { entities: EntityReport[] }) {
  const redacted = entities.filter((entity) => entity.was_redacted);
  const located = redacted.filter((entity) => entity.bbox);
  const pages = new Map<number, { total: number; located: number; confidence: number }>();
  const categories = new Map<string, number>();
  for (const entity of redacted) {
    const page = entity.page_number ?? 1;
    const current = pages.get(page) ?? { total: 0, located: 0, confidence: 0 };
    current.total += 1;
    current.located += entity.bbox ? 1 : 0;
    current.confidence += entity.confidence;
    pages.set(page, current);
    categories.set(entity.entity_type, (categories.get(entity.entity_type) ?? 0) + 1);
  }
  const pageRows = [...pages.entries()].sort(([left], [right]) => left - right);
  const categoryRows = [...categories.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 6);

  if (!redacted.length) return null;
  return (
    <div className="mb-4 grid gap-3 lg:grid-cols-2">
      <div className="rounded-lg border bg-muted/20 p-3 text-xs">
        <p className="mb-2 font-semibold">Per-page coverage</p>
        <div className="space-y-1.5">
          {pageRows.map(([page, stats]) => (
            <div key={page} className="flex items-center justify-between gap-2">
              <span>Page {page}</span>
              <span className="text-muted-foreground">
                {stats.located}/{stats.total} mapped · avg {pct(stats.confidence / stats.total)}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border bg-muted/20 p-3 text-xs">
        <p className="mb-2 font-semibold">Most-redacted categories</p>
        <div className="space-y-1.5">
          {categoryRows.map(([category, count]) => (
            <div key={category} className="flex items-center justify-between gap-2">
              <span className="font-mono">{category}</span>
              <span className="text-muted-foreground">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function fileExtension(fileType: FileType | undefined): string {
  const extensions: Record<FileType, string> = {
    pdf: "pdf",
    docx: "docx",
    xlsx: "xlsx",
    jpeg: "jpg",
    png: "png",
    tiff: "tiff",
    dicom: "dcm",
    eml: "eml",
    mbox: "mbox",
  };
  return fileType ? extensions[fileType] : "bin";
}

function RiskBadge({ risk, large }: { risk: "low" | "medium" | "high"; large?: boolean }) {
  const map = {
    low: {
      cls: "border-success/40 bg-success/10 text-success",
      label: "Low re-identification risk",
    },
    medium: {
      cls: "border-warning/40 bg-warning/10 text-warning-foreground",
      label: "Medium re-identification risk",
    },
    high: {
      cls: "border-destructive/40 bg-destructive/10 text-destructive",
      label: "High re-identification risk",
    },
  };
  const m = map[risk];
  return (
    <Badge
      variant="outline"
      className={`${m.cls} ${large ? "px-4 py-1.5 text-sm" : "text-[10px]"}`}
    >
      {m.label}
    </Badge>
  );
}

function ReportPanel({
  report,
  jobId,
  onFeedbackSent,
}: {
  report: import("@/lib/api/types").RedactionReport;
  jobId: string;
  onFeedbackSent: () => void;
}) {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [pageFilter, setPageFilter] = useState<string>("all");
  const [detectorFilter, setDetectorFilter] = useState<string>("all");
  const [privilegeFilter, setPrivilegeFilter] = useState<string>("all");
  const [minConf, setMinConf] = useState(0);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [reportDownloadErr, setReportDownloadErr] = useState<unknown>(null);
  const [sortBy, setSortBy] = useState<"confidence" | "page" | "type" | "detector" | "privilege">(
    "confidence",
  );

  const filtered = useMemo(() => {
    let list = report.entities.filter((e) => {
      if (category !== "all" && e.entity_type !== category) return false;
      if (statusFilter === "redacted" && !e.was_redacted) return false;
      if (statusFilter === "reviewed" && e.was_redacted) return false;
      if (pageFilter !== "all" && String(e.page_number ?? "none") !== pageFilter) return false;
      if (detectorFilter !== "all" && !e.detector_source.includes(detectorFilter)) return false;
      if (privilegeFilter === "privileged" && !e.privileged_flag) return false;
      if (privilegeFilter === "not_privileged" && e.privileged_flag) return false;
      if (e.confidence < minConf) return false;
      if (
        q &&
        !e.entity_type.toLowerCase().includes(q.toLowerCase()) &&
        !e.explanation_text.toLowerCase().includes(q.toLowerCase())
      )
        return false;
      return true;
    });
    list = [...list].sort((a, b) => {
      if (sortBy === "confidence") return b.confidence - a.confidence;
      if (sortBy === "page") return (a.page_number ?? 0) - (b.page_number ?? 0);
      if (sortBy === "detector")
        return (a.detector_source[0] ?? "").localeCompare(b.detector_source[0] ?? "");
      if (sortBy === "privilege") return Number(b.privileged_flag) - Number(a.privileged_flag);
      return a.entity_type.localeCompare(b.entity_type);
    });
    return list;
  }, [
    report.entities,
    q,
    category,
    statusFilter,
    pageFilter,
    detectorFilter,
    privilegeFilter,
    minConf,
    sortBy,
  ]);

  const chartData = useMemo(() => {
    const counts: Record<string, { redacted: number; reviewed: number }> = {};
    report.entities.forEach((e) => {
      counts[e.entity_type] ??= { redacted: 0, reviewed: 0 };
      if (e.was_redacted) counts[e.entity_type].redacted++;
      else counts[e.entity_type].reviewed++;
    });
    return Object.entries(counts)
      .map(([type, v]) => ({ type, ...v }))
      .sort((a, b) => b.redacted + b.reviewed - (a.redacted + a.reviewed))
      .slice(0, 10);
  }, [report.entities]);

  const qaPct = report.entity_count ? (report.redacted_count / report.entity_count) * 100 : 100;

  async function downloadReport() {
    setDownloadingReport(true);
    setReportDownloadErr(null);
    try {
      const { blob, filename } = await redactionApi.downloadReport(jobId);
      triggerDownload(blob, filename ?? `medvault_redaction_report_${jobId}.pdf`);
      toast.success("PDF report downloaded");
    } catch (e) {
      setReportDownloadErr(e);
    } finally {
      setDownloadingReport(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-semibold">Report summary</h3>
          <p className="text-xs text-muted-foreground">
            Export includes summary metrics, charts, risk analysis, and all safe entity findings.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={downloadReport}
          disabled={downloadingReport}
        >
          <Download className="h-4 w-4" />
          {downloadingReport ? "Preparing PDF…" : "Download PDF report"}
        </Button>
      </div>
      {reportDownloadErr ? (
        <ErrorBanner error={reportDownloadErr} title="Report download failed" />
      ) : null}
      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-4">
        <SummaryStat label="Entities detected" value={report.entity_count} accent="chart-1" />
        <SummaryStat label="Redacted" value={report.redacted_count} accent="chart-2" />
        <SummaryStat
          label="Reviewed, kept"
          value={report.reviewed_not_redacted_count}
          accent="chart-3"
        />
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Redaction ratio</div>
          <div className="mt-2 h-24">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                innerRadius="70%"
                outerRadius="100%"
                data={[{ name: "r", value: qaPct, fill: "var(--chart-2)" }]}
                startAngle={90}
                endAngle={90 - (qaPct * 360) / 100}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                <RadialBar background dataKey="value" cornerRadius={8} />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
          <div className="text-center font-display text-lg font-bold">{qaPct.toFixed(0)}%</div>
        </Card>
      </div>

      {/* Category chart */}
      <Card className="p-4">
        <h3 className="mb-3 font-display font-semibold">Top entity categories</h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="type"
                width={140}
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              />
              <Bar
                dataKey="redacted"
                stackId="a"
                fill="var(--chart-1)"
                radius={[0, 0, 0, 0]}
                name="Redacted"
              />
              <Bar
                dataKey="reviewed"
                stackId="a"
                fill="var(--chart-4)"
                radius={[0, 4, 4, 0]}
                name="Kept"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <Label className="text-xs">Search</Label>
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type / explanation"
            />
          </div>
          <div>
            <Label className="text-xs">Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {Array.from(new Set(report.entities.map((e) => e.entity_type))).map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Status</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="redacted">Redacted</SelectItem>
                <SelectItem value="reviewed">Reviewed, kept</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Page</Label>
            <Select value={pageFilter} onValueChange={setPageFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All pages</SelectItem>
                {Array.from(new Set(report.entities.map((e) => String(e.page_number ?? "none"))))
                  .sort((a, b) => Number(a) - Number(b))
                  .map((page) => (
                    <SelectItem key={page} value={page}>
                      {page === "none" ? "No page" : `Page ${page}`}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Detector source</Label>
            <Select value={detectorFilter} onValueChange={setDetectorFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All detectors</SelectItem>
                {Array.from(new Set(report.entities.flatMap((e) => e.detector_source))).map(
                  (detector) => (
                    <SelectItem key={detector} value={detector}>
                      {detector}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Privilege</Label>
            <Select value={privilegeFilter} onValueChange={setPrivilegeFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All privilege states</SelectItem>
                <SelectItem value="privileged">Privileged only</SelectItem>
                <SelectItem value="not_privileged">Not privileged</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Min confidence: {pct(minConf)}</Label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minConf}
              onChange={(e) => setMinConf(parseFloat(e.target.value))}
              className="mt-3 w-full"
            />
          </div>
          <div>
            <Label className="text-xs">Sort</Label>
            <Select
              value={sortBy}
              onValueChange={(v) =>
                setSortBy(v as "confidence" | "page" | "type" | "detector" | "privilege")
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="confidence">Confidence</SelectItem>
                <SelectItem value="page">Page</SelectItem>
                <SelectItem value="type">Type</SelectItem>
                <SelectItem value="detector">Detector source</SelectItem>
                <SelectItem value="privilege">Privilege first</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {/* Entities */}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Showing {filtered.length} of {report.entity_count} entities
        </p>
        <div className="space-y-2">
          {filtered.slice(0, 100).map((e) => (
            <EntityRow
              key={e.id}
              entity={e}
              jobId={jobId}
              documentId={report.job.document_id}
              onFeedbackSent={onFeedbackSent}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function SummaryStat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className="mt-1 font-display text-3xl font-bold"
        style={{ color: `var(--color-${accent})` }}
      >
        {value}
      </div>
    </Card>
  );
}

function EntityRow({
  entity,
  jobId,
  documentId,
  onFeedbackSent,
}: {
  entity: EntityReport;
  jobId: string;
  documentId: string;
  onFeedbackSent: () => void;
}) {
  const [busy, setBusy] = useState<"correct" | "false_positive" | null>(null);
  async function feedback(verdict: "correct" | "false_positive") {
    setBusy(verdict);
    try {
      const fb: ExistingEntityFeedback = { job_id: jobId, entity_id: entity.id, verdict };
      await redactionApi.feedback(documentId, fb);
      toast.success(`Marked as ${verdict === "correct" ? "correct" : "false positive"}`);
      onFeedbackSent();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <Card className="p-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px]">
              {entity.entity_type}
            </Badge>
            {entity.privileged_flag ? (
              <Badge
                variant="outline"
                className="border-warning/50 bg-warning/10 text-warning-foreground text-[10px]"
              >
                <Gavel className="mr-1 h-3 w-3" /> Privileged
              </Badge>
            ) : null}
            {entity.was_redacted ? (
              <Badge
                variant="outline"
                className="border-success/40 bg-success/10 text-success text-[10px]"
              >
                Redacted
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px]">
                Kept
              </Badge>
            )}
            {entity.page_number != null ? (
              <span className="text-[10px] text-muted-foreground">Page {entity.page_number}</span>
            ) : null}
          </div>
          <p className="mt-2 text-sm">{entity.explanation_text}</p>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Detectors: {entity.detector_source.join(", ") || "—"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="text-right">
            <div className="text-[10px] text-muted-foreground">Confidence</div>
            <div className="font-mono text-sm font-semibold">{pct(entity.confidence)}</div>
          </div>
          <div className="flex gap-1">
            <Button
              size="icon"
              variant="outline"
              className="h-8 w-8"
              onClick={() => feedback("correct")}
              disabled={!!busy}
              aria-label="Mark correct"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              className="h-8 w-8"
              onClick={() => feedback("false_positive")}
              disabled={!!busy}
              aria-label="Mark false positive"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

function MissedFeedbackForm({
  jobId,
  documentId,
  onSent,
}: {
  jobId: string;
  documentId: string;
  onSent: () => void;
}) {
  const [entityType, setEntityType] = useState<string>("PERSON");
  const [page, setPage] = useState(1);
  const [note, setNote] = useState("");
  const [includeRegion, setIncludeRegion] = useState(false);
  const [region, setRegion] = useState({ x0: 0, y0: 0, x1: 1, y1: 1 });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function submit() {
    setErr(null);
    if (includeRegion && (region.x1 <= region.x0 || region.y1 <= region.y0)) {
      setErr(new Error("Region x1/y1 must be greater than x0/y0."));
      return;
    }
    setBusy(true);
    try {
      const fb: MissedFeedback = {
        job_id: jobId,
        verdict: "missed",
        entity_type: entityType,
        page_number: page,
        bbox: includeRegion ? region : null,
        note: note || null,
      };
      await redactionApi.feedback(documentId, fb);
      toast.success("Missed-item feedback recorded");
      setNote("");
      onSent();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-3 flex items-center gap-2">
        <Flag className="h-4 w-4 text-primary" />
        <h3 className="font-display font-semibold">Report a missed item</h3>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Feedback contains no raw PHI — it safely calibrates future confidence for your account.
      </p>
      {err ? <ErrorBanner error={err} /> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label>Entity category</Label>
          <Select value={entityType} onValueChange={setEntityType}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-64">
              {ENTITY_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Page number</Label>
          <Input
            type="number"
            min={1}
            value={page}
            onChange={(e) => setPage(Math.max(1, parseInt(e.target.value) || 1))}
          />
        </div>
      </div>
      <div className="mt-3 rounded-lg border p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox
            checked={includeRegion}
            onCheckedChange={(checked) => setIncludeRegion(checked === true)}
          />
          Include an optional page region
        </label>
        <p className="mt-1 text-xs text-muted-foreground">
          Enter coordinates from the page preview or an external document viewer. No raw text is
          submitted.
        </p>
        {includeRegion ? (
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(["x0", "y0", "x1", "y1"] as const).map((coordinate) => (
              <div key={coordinate}>
                <Label htmlFor={`region-${coordinate}`}>{coordinate}</Label>
                <Input
                  id={`region-${coordinate}`}
                  type="number"
                  step="any"
                  value={region[coordinate]}
                  onChange={(event) =>
                    setRegion((current) => ({
                      ...current,
                      [coordinate]: Number(event.target.value),
                    }))
                  }
                />
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-3">
        <Label>Note (optional)</Label>
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          placeholder="Optional context, no PHI"
        />
      </div>
      <Button className="mt-4" onClick={submit} disabled={busy}>
        {busy ? "Sending…" : "Send feedback"}
      </Button>
    </Card>
  );
}
