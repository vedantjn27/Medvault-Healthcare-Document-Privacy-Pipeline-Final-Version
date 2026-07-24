import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, type ChangeEvent, type DragEvent } from "react";
import { documentsApi } from "@/lib/api/client";
import { activityStore } from "@/lib/session/activity-store";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ErrorBanner } from "@/components/error-banner";
import { UploadCloud, FileText } from "lucide-react";
import { fmtBytes } from "@/lib/format";
import { toast } from "sonner";

export const Route = createFileRoute("/app/upload")({
  component: UploadPage,
  head: () => ({ meta: [{ title: "Upload — MedVault" }] }),
});

const ACCEPT = ".pdf,.docx,.xlsx,.jpg,.jpeg,.png,.tif,.tiff,.dcm,.dicom,.eml,.mbox";
const MAX_BYTES = 50 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(ACCEPT.split(","));

function UploadPage() {
  const nav = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [dragOver, setDragOver] = useState(false);

  function pick(f: File | null) {
    if (!f) return;
    const suffix = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(suffix)) {
      setErr(new Error(`${f.name} is not a supported file type.`));
      setFile(null);
      return;
    }
    if (f.size > MAX_BYTES) {
      setErr(new Error(`File exceeds the 50 MiB limit (${fmtBytes(f.size)}).`));
      setFile(null);
      return;
    }
    setErr(null);
    setFile(f);
  }

  async function upload() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    setProgress(0);
    try {
      const doc = await documentsApi.upload(file, setProgress);
      activityStore.add({
        kind: "document",
        id: doc.id,
        createdAt: Date.now(),
        label: doc.original_filename,
        status: doc.status,
      });
      toast.success("Document uploaded");
      nav({ to: "/app/documents/$documentId", params: { documentId: doc.id } });
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pick(f);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Upload a document</h1>
        <p className="mt-1 text-muted-foreground">
          PDF, DOCX, XLSX, JPEG, PNG, TIFF, DICOM, EML, MBOX — up to 50 MiB.
        </p>
      </div>

      {err ? <ErrorBanner error={err} /> : null}

      <Card
        className={`relative overflow-hidden border-2 border-dashed transition-all ${dragOver ? "border-primary bg-primary/5" : "border-border"}`}
        onDrop={onDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
      >
        <label className="flex cursor-pointer flex-col items-center justify-center gap-4 p-10 text-center">
          <div className="grid h-16 w-16 place-items-center rounded-2xl gradient-hero shadow-glow">
            <UploadCloud className="h-8 w-8 text-white" />
          </div>
          {file ? (
            <div>
              <div className="flex items-center justify-center gap-2 font-medium">
                <FileText className="h-4 w-4" /> {file.name}
              </div>
              <p className="text-xs text-muted-foreground">{fmtBytes(file.size)}</p>
            </div>
          ) : (
            <>
              <div>
                <p className="font-medium">Drop a file here or click to browse</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Backend validates real content — extension alone is not enough.
                </p>
              </div>
            </>
          )}
          <input
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e: ChangeEvent<HTMLInputElement>) => pick(e.target.files?.[0] ?? null)}
          />
        </label>
      </Card>

      {busy ? (
        <div>
          <Progress value={progress} />
          <p className="mt-2 text-center text-xs text-muted-foreground" aria-live="polite">
            Uploading… {progress}%
          </p>
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => {
            setFile(null);
            setProgress(0);
          }}
        >
          Reset
        </Button>
        <Button onClick={upload} disabled={!file || busy}>
          {busy ? "Uploading…" : "Upload & continue"}
        </Button>
      </div>

      <Card className="border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground">
        Files and outputs are ephemeral. Previews are marked pre-redaction and never persisted.
        Completed single-file outputs can be downloaded again during this authenticated session.
      </Card>
    </div>
  );
}
