import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { documentsApi, redactionApi } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import { usePrivacyMode } from "@/lib/session/privacy-mode-context";
import type { PrivacyMode, Verbosity } from "@/lib/api/types";
import { ENTITY_TYPES, PRIVACY_MODE_DESCRIPTIONS, PRIVACY_MODE_LABELS } from "@/lib/api/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorBanner } from "@/components/error-banner";
import { DocumentPreview } from "@/components/document-preview";
import { CapsuleLoader } from "@/components/capsule-loader";
import { fmtBytes, relativeTime } from "@/lib/format";
import { StatusBadge } from "@/routes/app.index";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertTriangle,
  Clock,
  FileType2,
  GitCompareArrows,
  History,
  Play,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/app/documents/$documentId")({
  component: DocumentWorkspace,
});

function DocumentWorkspace() {
  const { documentId } = Route.useParams();
  const nav = useNavigate();

  const docQ = useQuery({
    queryKey: ["doc", documentId],
    queryFn: () => documentsApi.get(documentId),
    refetchInterval: (q) => {
      const online = typeof navigator === "undefined" || navigator.onLine;
      return online && q.state.data?.status === "processing" ? 3000 : false;
    },
  });
  const previewQ = useQuery({
    queryKey: ["preview", documentId],
    queryFn: () => documentsApi.preview(documentId),
    retry: 1,
  });

  const { mode, setMode, customRules, setCustomRules } = usePrivacyMode();
  const [verbosity, setVerbosity] = useState<Verbosity>("standard");
  const [subjectId, setSubjectId] = useState("");
  const [running, setRunning] = useState(false);
  const [runErr, setRunErr] = useState<unknown>(null);
  const runKey = useRef(crypto.randomUUID());

  const canRun =
    mode !== "custom" ||
    (customRules.entity_types_to_redact.length >= 1 &&
      !customRules.entity_types_to_redact.some((entity) =>
        customRules.entity_types_to_preserve.includes(entity),
      ));

  async function runRedaction() {
    setRunErr(null);
    setRunning(true);
    try {
      const job = await redactionApi.run(
        {
          document_id: documentId,
          privacy_mode: mode,
          verbosity,
          custom_rules: mode === "custom" ? customRules : null,
          subject_patient_id: mode === "patient_portal" && subjectId ? subjectId : null,
        },
        runKey.current,
      );
      activityStore.add({
        kind: "job",
        id: job.job_id,
        createdAt: Date.now(),
        documentId,
        privacyMode: job.privacy_mode,
        status: job.status,
        label: `${PRIVACY_MODE_LABELS[job.privacy_mode]} — ${documentId.slice(-6)}`,
      });
      toast.success("Redaction job started");
      nav({ to: "/app/jobs/$jobId", params: { jobId: job.job_id } });
    } catch (e) {
      setRunErr(e);
    } finally {
      setRunning(false);
    }
  }

  const doc = docQ.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">Document</p>
          <h1 className="truncate font-display text-2xl font-bold sm:text-3xl">
            {doc?.original_filename ?? <Skeleton className="inline-block h-8 w-64" />}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {doc ? <StatusBadge status={doc.status} /> : null}
            {doc ? (
              <Badge variant="outline" className="uppercase">
                <FileType2 className="mr-1 h-3 w-3" />
                {doc.file_type}
              </Badge>
            ) : null}
            {doc ? <span>{fmtBytes(doc.size_bytes)}</span> : null}
            {doc ? (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> Expires {relativeTime(doc.expires_at)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/app/compare" search={{ documentId } as never}>
            <Button variant="outline" size="sm" className="gap-2">
              <GitCompareArrows className="h-4 w-4" /> Compare modes
            </Button>
          </Link>
          <Link to="/app/audit" search={{ documentId } as never}>
            <Button variant="outline" size="sm" className="gap-2">
              <History className="h-4 w-4" /> Audit
            </Button>
          </Link>
        </div>
      </div>

      {docQ.error ? <ErrorBanner error={docQ.error} /> : null}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* PREVIEW */}
        <Card className="p-4 lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display font-semibold">Pre-redaction preview</h2>
            <Badge
              variant="outline"
              className="border-warning/40 bg-warning/10 text-warning-foreground"
            >
              <ShieldAlert className="mr-1 h-3 w-3" /> Sensitive · session-only
            </Badge>
          </div>
          {previewQ.isLoading ? (
            <div className="grid min-h-56 place-items-center rounded-xl border border-dashed bg-muted/20">
              <CapsuleLoader label="Preparing document preview…" />
            </div>
          ) : previewQ.error ? (
            <ErrorBanner error={previewQ.error} title="Preview unavailable" />
          ) : previewQ.data ? (
            <DocumentPreview
              data={previewQ.data}
              label="Original"
              loadPage={(pageNumber) => documentsApi.previewPage(documentId, pageNumber)}
            />
          ) : null}
        </Card>

        {/* CONFIG */}
        <Card className="p-4 lg:col-span-2">
          <h2 className="font-display font-semibold">Privacy mode</h2>
          <Select value={mode} onValueChange={(v) => setMode(v as PrivacyMode)}>
            <SelectTrigger className="mt-2">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(PRIVACY_MODE_LABELS) as PrivacyMode[]).map((m) => (
                <SelectItem key={m} value={m}>
                  {PRIVACY_MODE_LABELS[m]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="mt-2 text-xs text-muted-foreground">{PRIVACY_MODE_DESCRIPTIONS[mode]}</p>

          <div className="mt-4 space-y-2">
            <Label>Verbosity</Label>
            <Tabs value={verbosity} onValueChange={(v) => setVerbosity(v as Verbosity)}>
              <TabsList className="grid grid-cols-2">
                <TabsTrigger value="standard">Standard</TabsTrigger>
                <TabsTrigger value="entity_type">Entity type</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {mode === "patient_portal" ? (
            <div className="mt-4 space-y-2">
              <Label htmlFor="subject">Subject patient ID (optional)</Label>
              <Input
                id="subject"
                maxLength={128}
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                placeholder="Preserve this identifier"
              />
              <p className="text-xs text-muted-foreground">
                This exact identifier will survive; all others are redacted.
              </p>
            </div>
          ) : null}

          {mode === "custom" ? (
            <div className="mt-4 space-y-4">
              <div>
                <Label>Confidence threshold: {customRules.confidence_threshold.toFixed(2)}</Label>
                <Slider
                  min={0.4}
                  max={1}
                  step={0.01}
                  value={[customRules.confidence_threshold]}
                  onValueChange={([confidence_threshold]) =>
                    setCustomRules({ ...customRules, confidence_threshold })
                  }
                  className="mt-2"
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>Synthetic replacement</Label>
                  <p className="text-xs text-muted-foreground">
                    Replace with consistent placeholders
                  </p>
                </div>
                <Switch
                  checked={customRules.synthetic_replacement}
                  onCheckedChange={(synthetic_replacement) =>
                    setCustomRules({ ...customRules, synthetic_replacement })
                  }
                />
              </div>
              <div>
                <Label>Categories</Label>
                <p className="text-xs text-muted-foreground">
                  Toggle redact / preserve. Must have at least one redact.
                </p>
                <div className="mt-2 max-h-64 space-y-1 overflow-y-auto rounded-lg border p-2">
                  {ENTITY_TYPES.map((et) => {
                    const isRedact = customRules.entity_types_to_redact.includes(et);
                    const isPreserve = customRules.entity_types_to_preserve.includes(et);
                    return (
                      <div
                        key={et}
                        className="flex items-center justify-between gap-2 rounded px-2 py-1 text-xs hover:bg-muted/50"
                      >
                        <span className="font-mono">{et}</span>
                        <div className="flex items-center gap-3">
                          <label className="flex items-center gap-1">
                            <Checkbox
                              checked={isRedact}
                              onCheckedChange={(c) => {
                                setCustomRules({
                                  ...customRules,
                                  entity_types_to_redact: c
                                    ? [...new Set([...customRules.entity_types_to_redact, et])]
                                    : customRules.entity_types_to_redact.filter((x) => x !== et),
                                  entity_types_to_preserve: c
                                    ? customRules.entity_types_to_preserve.filter((x) => x !== et)
                                    : customRules.entity_types_to_preserve,
                                });
                              }}
                            />
                            <span className="text-destructive">Redact</span>
                          </label>
                          <label className="flex items-center gap-1">
                            <Checkbox
                              checked={isPreserve}
                              onCheckedChange={(c) => {
                                setCustomRules({
                                  ...customRules,
                                  entity_types_to_preserve: c
                                    ? [...new Set([...customRules.entity_types_to_preserve, et])]
                                    : customRules.entity_types_to_preserve.filter((x) => x !== et),
                                  entity_types_to_redact: c
                                    ? customRules.entity_types_to_redact.filter((x) => x !== et)
                                    : customRules.entity_types_to_redact,
                                });
                              }}
                            />
                            <span className="text-success">Keep</span>
                          </label>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : null}

          {runErr ? (
            <div className="mt-3">
              <ErrorBanner error={runErr} />
            </div>
          ) : null}

          <Button
            className="mt-4 w-full gap-2"
            onClick={runRedaction}
            disabled={!doc || running || !canRun}
          >
            <Play className="h-4 w-4" /> {running ? "Starting…" : "Run redaction"}
          </Button>

          {mode === "custom" && !canRun ? (
            <p className="mt-2 text-xs text-destructive">
              <AlertTriangle className="mr-1 inline h-3 w-3" /> Custom rules require ≥1 redact and
              no overlap with preserve.
            </p>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
