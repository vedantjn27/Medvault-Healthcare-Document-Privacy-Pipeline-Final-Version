import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { AuthShell } from "@/routes/auth.login";
import { ErrorBanner } from "@/components/error-banner";
import { CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/auth/register")({
  component: RegisterPage,
  head: () => ({ meta: [{ title: "Create account — MedVault" }] }),
});

const rules: { test: (s: string) => boolean; label: string }[] = [
  { test: (s) => s.length >= 12 && s.length <= 128, label: "12–128 characters" },
  { test: (s) => /[a-z]/.test(s), label: "One lowercase letter" },
  { test: (s) => /[A-Z]/.test(s), label: "One uppercase letter" },
  { test: (s) => /[0-9]/.test(s), label: "One number" },
  { test: (s) => /[^A-Za-z0-9]/.test(s), label: "One special character" },
];

function RegisterPage() {
  const auth = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [autoLogin, setAutoLogin] = useState(false);

  const valid = rules.every((r) => r.test(password)) && email.includes("@");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setErr(null);
    setBusy(true);
    try {
      await auth.register(email, password);
      if (autoLogin) {
        await auth.login(email, password);
        nav({ to: "/app" });
      } else {
        toast.success("Account created. Sign in to continue.");
        nav({ to: "/auth/login" });
      }
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
          <h1 className="font-display text-2xl font-bold">Create your account</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create an account to secure documents.
          </p>
        </div>
        <label className="flex items-start gap-2 rounded-lg border p-3 text-sm">
          <Checkbox
            checked={autoLogin}
            onCheckedChange={(checked) => setAutoLogin(checked === true)}
          />
          <span>
            Log me in automatically after registration
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Your JWT will be stored only for this browser session.
            </span>
          </span>
        </label>
        {err ? <ErrorBanner error={err} title="Registration failed" /> : null}
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
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <ul className="mt-2 grid gap-1 text-xs" aria-live="polite">
            {rules.map((r) => {
              const ok = r.test(password);
              return (
                <li
                  key={r.label}
                  className={
                    ok
                      ? "flex items-center gap-1.5 text-success"
                      : "flex items-center gap-1.5 text-muted-foreground"
                  }
                >
                  {ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" />
                  )}
                  {r.label}
                </li>
              );
            })}
          </ul>
        </div>
        <Button type="submit" className="w-full" disabled={busy || !valid}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/auth/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
