import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState, type ChangeEvent } from "react";
import { batchApi } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import { usePrivacyMode } from "@/lib/session/privacy-mode-context";
import type { PrivacyMode } from "@/lib/api/types";
import { PRIVACY_MODE_DESCRIPTIONS, PRIVACY_MODE_LABELS } from "@/lib/api/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ErrorBanner } from "@/components/error-banner";
import { UploadCloud, X, Layers } from "lucide-react";
import { fmtBytes } from "@/lib/format";
import { toast } from "sonner";

export const Route = createFileRoute("/app/batch/")({
  component: BatchIndexPage,
  head: () => ({ meta: [{ title: "Batch — MedVault" }] }),
});

const STANDARD: PrivacyMode[] = [
  "patient_portal",
  "research_sharing",
  "insurance_processing",
  "legal_discovery",
];
const ACCEPT = ".pdf,.docx,.xlsx,.jpg,.jpeg,.png,.tif,.tiff,.dcm,.dicom,.eml,.mbox";
const MAX = 25;
const MAX_BYTES = 50 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(ACCEPT.split(","));

function BatchIndexPage() {
  const nav = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const { mode, setMode } = usePrivacyMode();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState<unknown>(null);
  const batchKey = useRef(crypto.randomUUID());

  function pick(list: FileList | null) {
    if (!list) return;
    const selected = Array.from(list);
    const invalid = selected.find((file) => {
      const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      return !ALLOWED_EXTENSIONS.has(suffix) || file.size > MAX_BYTES;
    });
    if (invalid) {
      const suffix = invalid.name.slice(invalid.name.lastIndexOf(".")).toLowerCase();
      setErr(
        new Error(
          !ALLOWED_EXTENSIONS.has(suffix)
            ? `${invalid.name} is not a supported file type.`
            : `${invalid.name} exceeds the 50 MiB per-file limit.`,
        ),
      );
      return;
    }
    if (selected.length + files.length > MAX) {
      setErr(new Error(`A batch can contain at most ${MAX} files.`));
    } else {
      setErr(null);
    }
    const arr = selected.slice(0, MAX - files.length);
    setFiles((prev) => [...prev, ...arr].slice(0, MAX));
  }

  async function start() {
    if (!files.length || mode === "custom") return;
    setBusy(true);
    setErr(null);
    setProgress(0);
    try {
      const r = await batchApi.upload(files, mode, batchKey.current, setProgress);
      activityStore.add({
        kind: "batch",
        id: r.batch_job_id,
        createdAt: Date.now(),
        label: `Batch × ${r.items.length} (${PRIVACY_MODE_LABELS[mode]})`,
        privacyMode: mode,
        status: r.status,
      });
      toast.success("Batch started");
      nav({ to: "/app/batch/$batchId", params: { batchId: r.batch_job_id } });
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Batch processing</h1>
        <p className="mt-1 text-muted-foreground">
          Up to 25 files at once, one standard privacy mode per batch. Custom rules aren't supported
          in batch.
        </p>
      </div>

      {err ? <ErrorBanner error={err} /> : null}

      <Card className="p-6">
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Privacy mode</Label>
            <Select value={mode} onValueChange={(v) => setMode(v as PrivacyMode)}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STANDARD.map((m) => (
                  <SelectItem key={m} value={m}>
                    {PRIVACY_MODE_LABELS[m]}
                  </SelectItem>
                ))}
                <SelectItem value="custom" disabled>
                  Custom (single document only)
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="mt-2 text-xs text-muted-foreground">{PRIVACY_MODE_DESCRIPTIONS[mode]}</p>
            {mode === "custom" ? (
              <p className="mt-2 text-xs font-medium text-destructive">
                Custom rules require a single-document workspace. Select a standard mode to start
                this batch.
              </p>
            ) : null}
          </div>
          <div className="flex items-end">
            <label className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 transition-colors hover:border-primary hover:bg-primary/5">
              <UploadCloud className="h-5 w-5" />
              <span className="text-sm">
                Add files ({files.length}/{MAX})
              </span>
              <input
                type="file"
                multiple
                accept={ACCEPT}
                className="hidden"
                onChange={(e: ChangeEvent<HTMLInputElement>) => pick(e.target.files)}
              />
            </label>
          </div>
        </div>

        {files.length ? (
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-2 text-left">Filename</th>
                  <th className="p-2 text-right">Size</th>
                  <th className="p-2" />
                </tr>
              </thead>
              <tbody>
                {files.map((f, i) => (
                  <tr key={i} className="border-t">
                    <td className="truncate p-2">{f.name}</td>
                    <td className="p-2 text-right text-xs text-muted-foreground">
                      {fmtBytes(f.size)}
                    </td>
                    <td className="p-2 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                        aria-label="Remove"
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
            <Layers className="mx-auto mb-2 h-8 w-8" />
            Add up to 25 files to redact them all with one privacy mode.
          </div>
        )}

        {busy ? (
          <div role="status" aria-live="polite">
            <Progress value={progress} className="mt-4" />
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Uploading batch… {progress}%
            </p>
          </div>
        ) : null}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setFiles([])} disabled={busy || !files.length}>
            Clear
          </Button>
          <Button onClick={start} disabled={busy || !files.length || mode === "custom"}>
            {busy ? "Uploading…" : `Start batch (${files.length})`}
          </Button>
        </div>
      </Card>
    </div>
  );
}
