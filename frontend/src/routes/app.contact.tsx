import { createFileRoute } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Mail, Linkedin, HeartPulse, ShieldCheck, Github, Server, Phone } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { healthApi } from "@/lib/api/client";
import trustHandshake from "@/assets/contact/trust-handshake.png";

export const Route = createFileRoute("/app/contact")({
  component: ContactPage,
  head: () => ({ meta: [{ title: "Contact & Help — MedVault" }] }),
});

function ContactPage() {
  const [health, setHealth] = useState<"idle" | "checking" | "healthy" | "unreachable">("idle");

  async function checkBackend() {
    setHealth("checking");
    try {
      setHealth((await healthApi.check()) ? "healthy" : "unreachable");
    } catch {
      setHealth("unreachable");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold">Contact & help</h1>
        <p className="mt-1 text-muted-foreground">
          Reach the maintainer directly — happy to discuss integrations, feedback, or bug reports.
        </p>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="relative overflow-hidden p-8">
          <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/20 blur-3xl" />
          <div className="relative text-center">
            <blockquote className="mx-auto max-w-3xl font-display text-2xl font-bold leading-snug sm:text-3xl">
              <HeartPulse className="mx-auto mb-4 h-9 w-9 text-primary animate-pulse-glow" />
              &ldquo;Privacy is not a barrier to progress.
              <br />
              <span className="gradient-text">
                It is the foundation of trust in healthcare.&rdquo;
              </span>
            </blockquote>
          </div>
        </Card>
      </motion.div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <a href="mailto:vedantjain273@gmail.com">
          <Card className="group flex items-center gap-4 p-5 transition-all hover:border-primary/40 hover:shadow-glow">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground">
              <Mail className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground">Email</div>
              <div className="break-all font-medium">vedantjain273@gmail.com</div>
            </div>
          </Card>
        </a>
        <a href="tel:+919829896609">
          <Card className="group flex items-center gap-4 p-5 transition-all hover:border-primary/40 hover:shadow-glow">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground">
              <Phone className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Phone</div>
              <div className="font-medium">+91 98298 96609</div>
            </div>
          </Card>
        </a>
        <a
          href="https://www.linkedin.com/in/vedant-jain-858348318"
          target="_blank"
          rel="noreferrer"
        >
          <Card className="group flex items-center gap-4 p-5 transition-all hover:border-primary/40 hover:shadow-glow">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground">
              <Linkedin className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-muted-foreground">LinkedIn</div>
              <div className="font-medium">Vedant Jain</div>
            </div>
          </Card>
        </a>
      </div>

      <Card className="p-6">
        <h2 className="mb-3 flex items-center gap-2 font-display font-semibold">
          <ShieldCheck className="h-5 w-5 text-primary" /> Trusted support
        </h2>
        <p className="text-sm text-muted-foreground">
          Get help with integrations, feedback, document-processing questions, or an issue you
          encountered while using MedVault.
        </p>
        <img
          src={trustHandshake}
          alt="Handshake representing trusted support and healthcare privacy collaboration"
          className="mt-4 h-48 w-full rounded-xl border object-cover object-center"
        />
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t pt-4">
          <Button variant="outline" onClick={checkBackend} disabled={health === "checking"}>
            <Server className="mr-2 h-4 w-4" />
            {health === "checking" ? "Checking backend…" : "Test backend connection"}
          </Button>
          <span role="status" aria-live="polite" className="text-xs text-muted-foreground">
            {health === "healthy"
              ? "Backend health check passed."
              : health === "unreachable"
                ? "Backend health check failed or is unreachable."
                : "Uses the public /health endpoint."}
          </span>
        </div>
      </Card>

      <Card className="p-6 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <Github className="h-4 w-4" />
          Report issues, request features, or share test documents through the channels above.
          Please never send PHI unless a channel is confirmed HIPAA-compliant.
        </div>
      </Card>
    </div>
  );
}
