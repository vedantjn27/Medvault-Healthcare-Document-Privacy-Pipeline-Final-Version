import { createFileRoute, Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { ErrorBanner } from "@/components/error-banner";
import { ShieldCheck, Lock } from "lucide-react";
import { z } from "zod";

export const Route = createFileRoute("/auth/login")({
  validateSearch: z.object({ redirect: z.string().optional() }),
  component: LoginPage,
  head: () => ({ meta: [{ title: "Log in — MedVault" }] }),
});

function LoginPage() {
  const auth = useAuth();
  const nav = useNavigate();
  const { redirect } = useSearch({ from: "/auth/login" });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await auth.login(email, password);
      nav({ to: (redirect as "/app") ?? "/app" });
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <h1 className="font-display text-2xl font-bold">Welcome back</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in to continue securing clinical documents.
          </p>
        </div>
        {err ? <ErrorBanner error={err} title="Sign-in failed" /> : null}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          New to MedVault?{" "}
          <Link to="/auth/register" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* LEFT: brand panel */}
      <div className="relative hidden overflow-hidden gradient-hero lg:block">
        <div className="absolute inset-0 grid-pattern opacity-20" />
        <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-white/20 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-primary-glow/30 blur-3xl" />
        <div className="relative h-full p-12 text-white">
          <Link to="/" className="relative z-10 flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/20 backdrop-blur">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="font-display font-bold">MedVault</div>
              <div className="text-[10px] uppercase tracking-widest text-white/80">
                Privacy Pipeline
              </div>
            </div>
          </Link>
          <div className="auth-spline-stage">
            <iframe
              src="https://my.spline.design/visualicons-rfr5C3ZO3rtITx32SxxhYYf3/"
              title="Interactive healthcare privacy visual"
              allow="autoplay; fullscreen"
              allowFullScreen
            />
          </div>
          <div className="auth-slogan-tab">
            <span className="auth-slogan-copy">
              Privacy is not a barrier to progress. It is the foundation of trust in healthcare.
            </span>
          </div>
          <div className="sr-only">
            <Lock aria-hidden="true" />
            Ephemeral by design. QA fails closed.
          </div>
        </div>
      </div>
      {/* RIGHT: form */}
      <div className="relative flex flex-col">
        <div className="flex items-center justify-between p-4 lg:hidden">
          <Logo />
          <ThemeToggle />
        </div>
        <div className="absolute right-4 top-4 hidden lg:block">
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center p-6">
          <Card className="w-full max-w-md border-border/60 p-8 shadow-elegant">{children}</Card>
        </div>
      </div>
    </div>
  );
}
