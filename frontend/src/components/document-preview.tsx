import { useEffect, useState } from "react";
import { Expand, FileText, Table2 } from "lucide-react";
import type { PreviewResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CapsuleLoader } from "@/components/capsule-loader";

type PageLoader = (pageNumber: number) => Promise<{ blob: Blob }>;

export function DocumentPreview({
  data,
  label,
  loadPage,
}: {
  data: PreviewResponse;
  label: "Original" | "Redacted";
  loadPage?: PageLoader;
}) {
  const meta = Object.entries(data.metadata ?? {}).slice(0, 8);
  const [viewer, setViewer] = useState<
    | { kind: "page"; title: string; imageUrl: string; loading: boolean; error: string | null }
    | { kind: "text"; title: string; text: string }
    | null
  >(null);

  useEffect(() => {
    return () => {
      if (viewer?.kind === "page" && viewer.imageUrl.startsWith("blob:")) {
        URL.revokeObjectURL(viewer.imageUrl);
      }
    };
  }, [viewer]);

  async function openPage(page: Record<string, unknown>, index: number) {
    const pageNumber = typeof page.page_number === "number" ? page.page_number : index + 1;
    const fallback =
      (page.thumbnail as string | undefined) ?? (page.image as string | undefined) ?? "";
    setViewer({
      kind: "page",
      title: `${label} · page ${pageNumber}`,
      imageUrl: fallback,
      loading: !!loadPage,
      error: null,
    });
    if (!loadPage) return;
    try {
      const { blob } = await loadPage(pageNumber);
      const imageUrl = URL.createObjectURL(blob);
      setViewer((current) => {
        if (current?.kind === "page" && current.imageUrl.startsWith("blob:")) {
          URL.revokeObjectURL(current.imageUrl);
        }
        return {
          kind: "page",
          title: `${label} · page ${pageNumber}`,
          imageUrl,
          loading: false,
          error: null,
        };
      });
    } catch {
      setViewer((current) =>
        current?.kind === "page"
          ? {
              ...current,
              loading: false,
              error: "Full-resolution rendering is unavailable. Showing the preview image instead.",
            }
          : current,
      );
    }
  }

  return (
    <div className="space-y-4">
      {data.pages?.length ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {data.pages.slice(0, 9).map((page, index) => {
            const thumbnail =
              (page as { thumbnail?: string; image?: string }).thumbnail ??
              (page as { image?: string }).image;
            const pageNumber = typeof page.page_number === "number" ? page.page_number : index + 1;
            return (
              <button
                key={index}
                type="button"
                onClick={() => openPage(page, index)}
                className="group relative overflow-hidden rounded-lg border bg-muted text-left shadow-sm transition hover:border-primary hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary"
                aria-label={`Open ${label.toLowerCase()} document page ${pageNumber} at readable size`}
              >
                {thumbnail ? (
                  <img
                    src={thumbnail}
                    alt={`${label} document page ${pageNumber} preview`}
                    className="h-auto w-full"
                  />
                ) : (
                  <div className="grid aspect-[3/4] place-items-center text-xs text-muted-foreground">
                    Page {pageNumber}
                  </div>
                )}
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-background/90 px-2 py-1 text-[11px] font-medium backdrop-blur">
                  <span>Page {pageNumber}</span>
                  <span className="flex items-center gap-1 text-primary">
                    <Expand className="h-3 w-3" /> Open
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      ) : null}

      {data.text ? (
        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 text-xs font-semibold">
              <FileText className="h-3.5 w-3.5" /> Readable text preview
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() =>
                setViewer({ kind: "text", title: `${label} · readable text`, text: data.text! })
              }
            >
              <Expand className="mr-1 h-3.5 w-3.5" /> Open
            </Button>
          </div>
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-5">
            {data.text}
          </pre>
        </div>
      ) : null}

      {data.sheets?.length ? (
        <div className="space-y-3">
          {data.sheets.map((sheet, index) => {
            const rows = Array.isArray(sheet.rows)
              ? (sheet.rows as Array<Array<string | null>>)
              : [];
            return (
              <div key={index} className="overflow-auto rounded-lg border">
                <div className="flex items-center gap-1 border-b bg-muted/40 px-3 py-2 text-xs font-semibold">
                  <Table2 className="h-3.5 w-3.5" />
                  {typeof sheet.name === "string" ? sheet.name : `Sheet ${index + 1}`}
                </div>
                <table className="w-full text-xs">
                  <tbody>
                    {rows.map((row, rowIndex) => (
                      <tr key={rowIndex} className="border-b last:border-0">
                        {row.map((cell, cellIndex) => (
                          <td key={cellIndex} className="min-w-24 p-2 align-top">
                            {cell ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      ) : null}

      {data.messages?.length ? (
        <div className="space-y-2">
          {data.messages.slice(0, 5).map((message, index) => (
            <div key={index} className="rounded-lg border p-3 text-xs">
              <div className="grid gap-1 sm:grid-cols-2">
                {(["from", "to", "subject", "date"] as const).map((field) => (
                  <p key={field} className="truncate">
                    <span className="font-semibold capitalize">{field}:</span>{" "}
                    {String(message[field] ?? "")}
                  </p>
                ))}
              </div>
              {typeof message.body === "string" ? (
                <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-muted-foreground">
                  {message.body}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {meta.length ? (
        <div className="rounded-lg border p-3">
          <div className="mb-2 text-xs font-semibold">Metadata</div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {meta.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="truncate text-muted-foreground">{key}</dt>
                <dd className="truncate" title={String(value)}>
                  {String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      {data.truncated ? (
        <p className="text-xs text-warning-foreground">Preview truncated by the backend.</p>
      ) : null}
      {!data.pages.length && !data.text && !data.sheets.length && !data.messages.length ? (
        <p className="text-sm text-muted-foreground">No renderable preview content is available.</p>
      ) : null}

      <Dialog
        open={viewer !== null}
        onOpenChange={(open) => {
          if (!open) setViewer(null);
        }}
      >
        <DialogContent className="flex max-h-[95vh] max-w-[96vw] flex-col overflow-hidden p-4 sm:max-w-6xl">
          <DialogHeader className="pr-8">
            <DialogTitle>{viewer?.title}</DialogTitle>
            <DialogDescription>
              {viewer?.kind === "page"
                ? "Full-resolution authenticated preview. Use your browser zoom controls if needed."
                : "Readable authenticated preview. This content remains session-only."}
            </DialogDescription>
          </DialogHeader>
          {viewer?.kind === "page" ? (
            <div className="min-h-0 overflow-auto rounded-md border bg-muted/20 p-2">
              {viewer.loading ? (
                <div className="grid min-h-52 place-items-center p-8">
                  <CapsuleLoader label="Rendering readable page…" compact />
                </div>
              ) : null}
              {viewer.error ? (
                <p className="mb-2 text-xs text-warning-foreground">{viewer.error}</p>
              ) : null}
              {viewer.imageUrl ? (
                <img
                  src={viewer.imageUrl}
                  alt={viewer.title}
                  className="mx-auto h-auto max-w-none"
                />
              ) : null}
            </div>
          ) : viewer?.kind === "text" ? (
            <pre className="min-h-0 overflow-auto rounded-md border bg-muted/20 p-4 whitespace-pre-wrap font-mono text-sm leading-6">
              {viewer.text}
            </pre>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
