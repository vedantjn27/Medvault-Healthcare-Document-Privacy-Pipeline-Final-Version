import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { batchApi, triggerDownload } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { StatusBadge } from "@/routes/app.index";
import { ErrorBanner } from "@/components/error-banner";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, FileText, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/app/batch/$batchId")({
  component: BatchDetail,
});

function BatchDetail() {
  const { batchId } = Route.useParams();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => batchApi.status(batchId),
    refetchInterval: (r) => {
      const s = r.state.data?.status;
      const online = typeof navigator === "undefined" || navigator.onLine;
      return online && (s === "queued" || s === "processing") ? 3000 : false;
    },
  });
  const batch = q.data;
  const [dl, setDl] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function download() {
    setDl(true);
    setErr(null);
    try {
      const { blob, filename } = await batchApi.download(batchId);
      triggerDownload(blob, filename ?? `batch-${batchId}.zip`);
      activityStore.update("batch", batchId, { downloaded: true });
      toast.success("ZIP downloaded. Batch temp files removed server-side.");
      qc.invalidateQueries({ queryKey: ["batch", batchId] });
    } catch (e) {
      setErr(e);
    } finally {
      setDl(false);
    }
  }

  const totals = batch
    ? {
        complete: batch.items.filter((i) => i.status === "complete").length,
        failed: batch.items.filter((i) => i.status === "error" || i.status === "qa_failed").length,
        pending: batch.items.filter((i) => i.status === "queued" || i.status === "processing")
          .length,
      }
    : { complete: 0, failed: 0, pending: 0 };
  const totalPct = batch?.items.length
    ? ((totals.complete + totals.failed) / batch.items.length) * 100
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs text-muted-foreground">Batch job</p>
          <h1 className="font-display text-2xl font-bold sm:text-3xl">Batch redaction</h1>
          <div className="mt-2 flex items-center gap-2" aria-live="polite" aria-atomic="true">
            {batch ? <StatusBadge status={batch.status} /> : null}
            <span className="font-mono text-xs text-muted-foreground">{batchId}</span>
          </div>
        </div>
        <div>
          {batch?.status === "complete" ? (
            <Dialog>
              <DialogTrigger asChild>
                <Button className="gap-2 shadow-glow">
                  <Download className="h-4 w-4" /> Download ZIP
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>One-time batch export</DialogTitle>
                  <DialogDescription>
                    Downloading the ZIP deletes all related temporary document directories
                    server-side. A second download will fail with HTTP 410.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button onClick={download} disabled={dl}>
                    {dl ? "Downloading…" : "Download now"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>
      </div>

      {q.error ? <ErrorBanner error={q.error} /> : null}
      {err ? <ErrorBanner error={err} title="Download failed" /> : null}

      {batch ? (
        <>
          <Card className="p-6" aria-live="polite" aria-atomic="true">
            <div className="mb-3 grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="font-display text-2xl font-bold text-success">
                  {totals.complete}
                </div>
                <div className="text-xs text-muted-foreground">Complete</div>
              </div>
              <div>
                <div className="font-display text-2xl font-bold text-warning-foreground">
                  {totals.pending}
                </div>
                <div className="text-xs text-muted-foreground">Pending</div>
              </div>
              <div>
                <div className="font-display text-2xl font-bold text-destructive">
                  {totals.failed}
                </div>
                <div className="text-xs text-muted-foreground">Failed</div>
              </div>
            </div>
            <Progress value={totalPct} />
            <p className="mt-2 text-center text-xs text-muted-foreground">
              {Math.round(totalPct)}% items reached a terminal state
            </p>
          </Card>

          <Card className="p-0">
            <div className="p-4 font-display font-semibold">Items ({batch.items.length})</div>
            <ul className="divide-y">
              {batch.items.map((it, i) => (
                <li key={i} className="flex flex-wrap items-center gap-3 p-4">
                  <div className="grid h-8 w-8 place-items-center rounded-lg bg-muted">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-mono text-xs">{it.document_id}</div>
                    {it.error_message ? (
                      <div className="text-xs text-destructive">{it.error_message}</div>
                    ) : null}
                  </div>
                  <StatusBadge status={it.status} />
                  {it.redaction_job_id ? (
                    <Link to="/app/jobs/$jobId" params={{ jobId: it.redaction_job_id }}>
                      <Button size="sm" variant="ghost" className="gap-1">
                        Report <ArrowRight className="h-3 w-3" />
                      </Button>
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : (
        <div role="status" aria-live="polite">
          <p className="mb-2 text-sm text-muted-foreground">Loading batch status…</p>
          <Skeleton className="h-64" />
        </div>
      )}
    </div>
  );
}
