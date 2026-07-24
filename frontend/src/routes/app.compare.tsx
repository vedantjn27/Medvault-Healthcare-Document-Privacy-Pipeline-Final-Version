import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState, type ChangeEvent } from "react";
import { documentsApi, redactionApi } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import type { PrivacyMode, ModeComparisonResponse } from "@/lib/api/types";
import { PRIVACY_MODE_LABELS } from "@/lib/api/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorBanner } from "@/components/error-banner";
import { DocumentPreview } from "@/components/document-preview";
import { Progress } from "@/components/ui/progress";
import { GitCompareArrows, Loader2, ArrowRight, Trophy, UploadCloud, FileText } from "lucide-react";
import { toast } from "sonner";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { z } from "zod";

export const Route = createFileRoute("/app/compare")({
  validateSearch: z.object({ documentId: z.string().optional() }),
  component: ComparePage,
  head: () => ({ meta: [{ title: "Mode Comparison — MedVault" }] }),
});

const STANDARD: Exclude<PrivacyMode, "custom">[] = [
  "patient_portal",
  "research_sharing",
  "insurance_processing",
  "legal_discovery",
];

function ComparePage() {
  const { documentId: initialDocId } = useSearch({ from: "/app/compare" });
  const [documentId, setDocumentId] = useState(initialDocId ?? "");
  const [selected, setSelected] = useState<Exclude<PrivacyMode, "custom">[]>([
    "patient_portal",
    "research_sharing",
  ]);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [err, setErr] = useState<unknown>(null);
  const [result, setResult] = useState<ModeComparisonResponse | null>(null);

  const originalPreviewQ = useQuery({
    queryKey: ["compare", documentId, "original-preview"],
    queryFn: () => documentsApi.preview(documentId),
    enabled: !!result && !!documentId,
    retry: 1,
  });
  const modeEntries = result ? Object.entries(result.modes) : [];
  const modePreviewQs = useQueries({
    queries: modeEntries.map(([mode, info]) => ({
      queryKey: ["compare", info.job_id, "preview"],
      queryFn: () => redactionApi.outputPreview(info.job_id),
      enabled: !!result,
      retry: 1,
      meta: { mode },
    })),
  });

  function toggle(m: Exclude<PrivacyMode, "custom">) {
    setSelected((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));
  }

  async function uploadForComparison() {
    if (!file) return;
    setUploading(true);
    setUploadProgress(0);
    setErr(null);
    setResult(null);
    try {
      const document = await documentsApi.upload(file, setUploadProgress);
      setDocumentId(document.id);
      activityStore.add({
        kind: "document",
        id: document.id,
        createdAt: Date.now(),
        label: document.original_filename,
        status: document.status,
      });
      toast.success("Document uploaded. Choose modes and start the comparison.");
    } catch (e) {
      setErr(e);
    } finally {
      setUploading(false);
    }
  }

  async function run() {
    if (selected.length < 2 || selected.length > 5 || !documentId) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await redactionApi.compareModes({ document_id: documentId, modes: selected });
      setResult(r);
      Object.entries(r.modes).forEach(([m, info]) => {
        activityStore.add({
          kind: "job",
          id: info.job_id,
          createdAt: Date.now(),
          documentId,
          privacyMode: m,
          status: "complete",
          label: `${PRIVACY_MODE_LABELS[m as PrivacyMode]} (compare)`,
        });
      });
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  const chartData = result
    ? Object.entries(result.modes).map(([m, info]) => ({
        mode: PRIVACY_MODE_LABELS[m as PrivacyMode],
        redacted: info.redacted_count,
        diff: result.redacted_count_difference_from_baseline[m] ?? 0,
      }))
    : [];

  const categoryData = result
    ? (() => {
        const allCats = new Set<string>();
        Object.values(result.modes).forEach((info) =>
          Object.keys(info.entity_type_counts).forEach((c) => allCats.add(c)),
        );
        return Array.from(allCats)
          .slice(0, 12)
          .map((cat) => {
            const row: Record<string, string | number> = { category: cat };
            Object.entries(result.modes).forEach(([m, info]) => {
              row[PRIVACY_MODE_LABELS[m as PrivacyMode]] = info.entity_type_counts[cat] ?? 0;
            });
            return row;
          });
      })()
    : [];

  const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Mode comparison</h1>
        <p className="mt-1 text-muted-foreground">
          Run two to five standard modes against the same document. Missing runs are executed
          automatically.
        </p>
      </div>

      <Card className="p-6">
        <div className="mb-5 rounded-lg border border-dashed p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <Label htmlFor="compare-file">Upload a document for comparison</Label>
              <p className="mt-1 text-xs text-muted-foreground">
                PDF, DOCX, XLSX, images, DICOM, EML, or MBOX — up to 50 MiB.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="cursor-pointer">
                <span className="sr-only">Choose document for mode comparison</span>
                <input
                  id="compare-file"
                  type="file"
                  accept=".pdf,.docx,.xlsx,.jpg,.jpeg,.png,.tif,.tiff,.dcm,.dicom,.eml,.mbox"
                  className="hidden"
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setFile(event.target.files?.[0] ?? null);
                    setResult(null);
                  }}
                />
                <Button variant="outline" size="sm" className="gap-2" asChild>
                  <span>
                    <UploadCloud className="h-4 w-4" /> Choose file
                  </span>
                </Button>
              </label>
              <Button onClick={uploadForComparison} disabled={!file || uploading} size="sm">
                {uploading ? "Uploading…" : "Upload for comparison"}
              </Button>
            </div>
          </div>
          {file ? (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileText className="h-3.5 w-3.5" /> {file.name}
            </p>
          ) : null}
          {uploading ? <Progress value={uploadProgress} className="mt-3" /> : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <Label>Document ID</Label>
            <Input
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="Paste a document ID from your session activity"
              className="font-mono text-xs"
            />
          </div>
          <div className="flex items-end">
            <Button
              className="w-full gap-2"
              onClick={run}
              disabled={busy || !documentId || selected.length < 2 || selected.length > 5}
            >
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Running…
                </>
              ) : (
                <>
                  <GitCompareArrows className="h-4 w-4" /> Compare
                </>
              )}
            </Button>
          </div>
        </div>

        <div className="mt-4">
          <Label>Modes (2–5)</Label>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {STANDARD.map((m) => (
              <label
                key={m}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 ${selected.includes(m) ? "border-primary bg-primary/5" : ""}`}
              >
                <Checkbox checked={selected.includes(m)} onCheckedChange={() => toggle(m)} />
                <span className="text-sm font-medium">{PRIVACY_MODE_LABELS[m]}</span>
              </label>
            ))}
          </div>
        </div>

        {busy ? (
          <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-4 text-xs text-muted-foreground">
            Generating missing runs. This can take as long as normal processing per mode — don't
            close the tab.
          </div>
        ) : null}
      </Card>

      {err ? <ErrorBanner error={err} title="Comparison failed" /> : null}

      {result ? (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-display font-semibold">Visual document comparison</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Original and actual generated outputs are shown side by side. Click any page to
                  inspect it at readable size.
                </p>
              </div>
              <Badge variant="outline">{modeEntries.length} modes selected</Badge>
            </div>
            <div className="mt-4 grid grid-flow-col auto-cols-[minmax(300px,1fr)] gap-4 overflow-x-auto pb-2">
              <div className="min-w-0 rounded-lg border border-warning/40 bg-warning/5 p-3">
                <Badge variant="outline" className="border-warning/40 bg-warning/10">
                  Original — sensitive
                </Badge>
                <div className="mt-3">
                  {originalPreviewQ.isLoading ? (
                    <Progress value={40} />
                  ) : originalPreviewQ.error ? (
                    <ErrorBanner
                      error={originalPreviewQ.error}
                      title="Original preview unavailable"
                    />
                  ) : originalPreviewQ.data ? (
                    <DocumentPreview
                      data={originalPreviewQ.data}
                      label="Original"
                      loadPage={(pageNumber) => documentsApi.previewPage(documentId, pageNumber)}
                    />
                  ) : null}
                </div>
              </div>
              {modeEntries.map(([mode, info], index) => {
                const previewQ = modePreviewQs[index];
                return (
                  <div
                    key={info.job_id}
                    className="min-w-0 rounded-lg border border-success/30 bg-success/5 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge
                        variant="outline"
                        className="border-success/40 bg-success/10 text-success"
                      >
                        {PRIVACY_MODE_LABELS[mode as PrivacyMode]}
                      </Badge>
                      <Badge variant="outline">{info.redacted_count}</Badge>
                    </div>
                    <div className="mt-3">
                      {previewQ?.isLoading ? (
                        <Progress value={40} />
                      ) : previewQ?.error ? (
                        <ErrorBanner error={previewQ.error} title="Mode preview unavailable" />
                      ) : previewQ?.data ? (
                        <DocumentPreview
                          data={previewQ.data}
                          label="Redacted"
                          loadPage={(pageNumber) =>
                            redactionApi.outputPreviewPage(info.job_id, pageNumber)
                          }
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
          <Card className="p-6">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-display font-semibold">Total redactions per mode</h3>
              <Badge variant="outline" className="gap-1">
                <Trophy className="h-3 w-3" /> Baseline:{" "}
                {PRIVACY_MODE_LABELS[result.baseline_mode as PrivacyMode]}
              </Badge>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="mode" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar
                    dataKey="redacted"
                    fill="var(--chart-1)"
                    radius={[6, 6, 0, 0]}
                    name="Redacted"
                  />
                  <Bar
                    dataKey="diff"
                    fill="var(--chart-3)"
                    radius={[6, 6, 0, 0]}
                    name="Δ from baseline"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {categoryData.length ? (
            <Card className="p-6">
              <h3 className="mb-3 font-display font-semibold">Category counts by mode</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} />
                    <YAxis
                      type="category"
                      dataKey="category"
                      width={140}
                      tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "var(--popover)",
                        border: "1px solid var(--border)",
                        fontSize: 12,
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {Object.keys(result.modes).map((m, i) => (
                      <Bar
                        key={m}
                        dataKey={PRIVACY_MODE_LABELS[m as PrivacyMode]}
                        fill={COLORS[i % COLORS.length]}
                        radius={[0, 4, 4, 0]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          ) : null}

          <Card className="p-6">
            <h3 className="mb-3 font-display font-semibold">Per-mode details</h3>
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(result.modes).map(([m, info]) => (
                <div key={m} className="rounded-lg border p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="font-medium">{PRIVACY_MODE_LABELS[m as PrivacyMode]}</div>
                    <Badge variant="outline">{info.redacted_count} redacted</Badge>
                  </div>
                  <p className="text-[10px] font-mono text-muted-foreground truncate">
                    {info.job_id}
                  </p>
                  <Link to="/app/jobs/$jobId" params={{ jobId: info.job_id }}>
                    <Button variant="ghost" size="sm" className="mt-2 gap-1">
                      Open report <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
