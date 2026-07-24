import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api/client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorBanner } from "@/components/error-banner";
import { Bell, BellRing, BellOff, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
  head: () => ({ meta: [{ title: "Notifications — MedVault" }] }),
});

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function SettingsPage() {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const vapid = (import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined) ?? "";

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (
      !("Notification" in window) ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window)
    ) {
      setPermission("unsupported");
      return;
    }
    setPermission(Notification.permission);
    void navigator.serviceWorker
      .getRegistration("/")
      .then((reg) => reg?.pushManager.getSubscription())
      .then((sub) => setSubscribed(!!sub))
      .catch(() => setSubscribed(false));
  }, []);

  async function enable() {
    setErr(null);
    setBusy(true);
    try {
      if (!vapid) throw new Error("VITE_VAPID_PUBLIC_KEY is not configured in the frontend .env");
      const reg = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") throw new Error("Notification permission was not granted.");
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapid),
        }));
      const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } };
      await authApi.subscribePush({
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      });
      setSubscribed(true);
      toast.success("Push notifications enabled");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setErr(null);
    try {
      const reg = await navigator.serviceWorker.getRegistration("/");
      const sub = await reg?.pushManager.getSubscription();
      await sub?.unsubscribe();
      await authApi.unsubscribePush();
      setSubscribed(false);
      toast.success("Notifications disabled for this browser.");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Notifications</h1>
        <p className="mt-1 text-muted-foreground">
          Get pinged the moment a redaction job finishes, in this browser only.
        </p>
      </div>

      {err ? <ErrorBanner error={err} /> : null}

      <Card className="p-6">
        <div className="flex items-start gap-4">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl gradient-hero shadow-glow">
            {subscribed ? (
              <BellRing className="h-6 w-6 text-white" />
            ) : (
              <Bell className="h-6 w-6 text-white" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-lg font-semibold">Browser push</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Uses the Web Push standard. Payload contains only a title and job ID — no PHI is ever
              pushed.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {permission === "unsupported" ? "Unsupported browser" : `Permission: ${permission}`}
              </Badge>
              {subscribed ? (
                <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                  <CheckCircle2 className="mr-1 h-3 w-3" /> Subscribed
                </Badge>
              ) : (
                <Badge variant="secondary">
                  <BellOff className="mr-1 h-3 w-3" /> Not subscribed
                </Badge>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              {!subscribed ? (
                <Button onClick={enable} disabled={busy || permission === "unsupported"}>
                  {busy ? "Enabling…" : "Enable notifications"}
                </Button>
              ) : (
                <Button variant="outline" onClick={disable} disabled={busy}>
                  {busy ? "Disabling…" : "Disable"}
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>

      <Card className="border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground">
        If push is unavailable or denied, status polling continues to work in-app. The backend also
        handles SMTP fallback automatically — no configuration needed here.
      </Card>
    </div>
  );
}
