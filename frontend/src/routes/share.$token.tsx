import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Download, FileLock2, LockKeyhole, ShieldCheck, Timer, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ErrorBanner } from "@/components/error-banner";
import { publicShareApi, triggerDownload } from "@/lib/api/client";

export const Route = createFileRoute("/share/$token")({
  component: SecureSharePage,
  head: () => ({ meta: [{ title: "Secure document share — MedVault" }] }),
});

function SecureSharePage() {
  const { token } = Route.useParams();
  const [password, setPassword] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const details = useQuery({
    queryKey: ["public-share", token, password],
    queryFn: () => publicShareApi.details(token, password || undefined),
    enabled: unlocked,
    retry: false,
  });
  const download = useMutation({
    mutationFn: () => publicShareApi.download(token, password || undefined),
    onSuccess: ({ blob, filename }) => triggerDownload(blob, filename),
  });

  function unlock(event: FormEvent) {
    event.preventDefault();
    setUnlocked(true);
    void details.refetch();
  }

  const share = details.data;
  return (
    <main className="app-surface grid min-h-screen place-items-center p-5">
      <div className="pointer-events-none fixed inset-0 grid-pattern opacity-20" />
      <Card className="relative w-full max-w-xl overflow-hidden border-primary/30 shadow-elegant">
        <div className="gradient-hero px-7 py-8 text-white">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white/85"><ShieldCheck className="h-4 w-4" /> MedVault secure share</div>
              <h1 className="font-display text-3xl font-bold">Privacy-safe document delivery</h1>
              <p className="mt-2 max-w-md text-sm text-white/80">This link provides a controlled redacted output only. No original document content is exposed here.</p>
            </div>
            <FileLock2 className="h-10 w-10 shrink-0 text-white/80" />
          </div>
        </div>
        <div className="p-6">
          {!share ? (
            <form className="space-y-4" onSubmit={unlock}>
              <div>
                <Label htmlFor="share-password">Share password</Label>
                <Input id="share-password" className="mt-2" type="password" value={password} onChange={(event) => { setPassword(event.target.value); setUnlocked(false); }} placeholder="Enter password if this link is protected" />
                <p className="mt-2 text-xs text-muted-foreground">If no password was supplied by the sender, leave this blank and continue.</p>
              </div>
              {details.error ? <ErrorBanner error={details.error instanceof TypeError ? new Error("Cannot reach the local MedVault API. Keep the backend running, then refresh this link.") : details.error} title="Unable to open secure share" /> : null}
              <Button className="w-full" type="submit" disabled={details.isFetching}><LockKeyhole className="mr-2 h-4 w-4" /> {details.isFetching ? "Verifying secure link…" : "Open secure share"}</Button>
            </form>
          ) : (
            <div className="space-y-5">
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Redacted file ready</p><h2 className="mt-1 break-all font-display text-xl font-semibold">{share.filename}</h2></div><Badge variant="secondary" className="gap-1"><Eye className="h-3.5 w-3.5" /> {share.role} access</Badge></div>
                <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2"><span className="flex items-center gap-1.5"><Timer className="h-3.5 w-3.5 text-primary" /> Expires {new Date(share.expires_at).toLocaleString()}</span><span>{share.max_accesses ? `${share.access_count}/${share.max_accesses} downloads used` : "No download count limit"}</span></div>
              </div>
              {share.allow_download ? <Button className="w-full" disabled={download.isPending} onClick={() => download.mutate()}><Download className="mr-2 h-4 w-4" /> {download.isPending ? "Preparing protected file…" : "Download redacted document"}</Button> : <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-sm text-muted-foreground">This is a review-only share. Downloading is disabled by its owner.</div>}
              {download.error ? <ErrorBanner error={download.error} title="Download unavailable" /> : null}
              <p className="text-center text-xs text-muted-foreground">Access is audited. This page never displays the original document.</p>
            </div>
          )}
          <div className="mt-6 border-t pt-4 text-center"><Link to="/" className="text-sm font-medium text-primary hover:underline">Return to MedVault</Link></div>
        </div>
      </Card>
    </main>
  );
}
