import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import {
  ArrowRight,
  CheckCircle2,
  FileSearch,
  HeartPulse,
  Landmark,
  Layers,
  Lock,
  Mail,
  Phone,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type AboutMedVaultProps = { inApp?: boolean };

const COMPLIANCE = [
  {
    icon: ShieldCheck,
    title: "HIPAA-ready safeguards",
    body: "Supports minimum-necessary handling through destructive PHI redaction, access-scoped APIs, auditability, and temporary storage controls.",
  },
  {
    icon: Landmark,
    title: "GDPR-aligned principles",
    body: "Built around data minimisation, purpose-specific privacy modes, storage limitation, and controlled access to derived outputs.",
  },
  {
    icon: FileSearch,
    title: "Auditability by design",
    body: "Hash-chained events make document actions, review decisions, shares, and downloads independently verifiable.",
  },
  {
    icon: Users,
    title: "Human accountability",
    body: "QA and human review gates prevent a redacted output from being distributed before its findings are resolved.",
  },
];

const SECURITY = [
  "Destructive text and pixel redaction rather than visual overlays",
  "Post-redaction QA that fails closed on residual sensitive data",
  "TTL-controlled temporary source and output storage",
  "JWT authentication, owner-scoped resources, and Argon2 password hashing",
  "Password-protected, expiring, revocable secure-share links",
  "No raw matched PHI stored in audit records or intelligence views",
];

const DIFFERENTIATORS = [
  { icon: Layers, title: "One pipeline, many formats", body: "PDF, office files, medical imaging, scanned images, and email archives are handled through one privacy workflow." },
  { icon: ScanSearch, title: "Explainable, not opaque", body: "Every safe finding can show category, confidence, detector source, page context, and review status." },
  { icon: Sparkles, title: "Privacy that fits the purpose", body: "Five privacy modes let the same document serve patient, research, insurance, legal, or custom operational needs." },
];

export function AboutMedVault({ inApp = false }: AboutMedVaultProps) {
  const primaryTarget = inApp ? "/app/upload" : "/auth/register";
  const primaryLabel = inApp ? "Redact a document" : "Experience MedVault";

  return (
    <div className="relative isolate overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[34rem] bg-[radial-gradient(ellipse_at_top,hsla(var(--primary)/0.22),transparent_62%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 grid-pattern opacity-25" />

      <section className="mx-auto max-w-6xl px-4 pb-14 pt-12 lg:px-8 lg:pt-20">
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="text-center">
          <Badge variant="outline" className="border-primary/40 bg-primary/10 px-3 py-1 text-primary"><ShieldCheck className="mr-1.5 h-3.5 w-3.5" /> Purpose-built healthcare privacy</Badge>
          <h1 className="mx-auto mt-6 max-w-4xl font-display text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">The trust layer between <span className="gradient-text">clinical data</span> and meaningful progress.</h1>
          <p className="mx-auto mt-6 max-w-3xl text-base leading-7 text-muted-foreground sm:text-lg">MedVault turns sensitive, multi-format healthcare documents into privacy-safe, reviewable outputs—without treating compliance, utility, or accountability as an afterthought.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3"><Link to={primaryTarget as "/app/upload"}><Button size="lg" className="gap-2 shadow-glow">{primaryLabel}<ArrowRight className="h-4 w-4" /></Button></Link><Link to={inApp ? "/app/audit" : "/auth/login" as "/auth/login"}><Button size="lg" variant="outline">{inApp ? "See audit trail" : "Sign in"}</Button></Link></div>
        </motion.div>

        <div className="mt-14 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="relative overflow-hidden border-primary/30 p-7 shadow-elegant sm:p-9"><div className="absolute -right-14 -top-14 h-52 w-52 rounded-full bg-primary/20 blur-3xl" /><div className="relative"><div className="grid h-12 w-12 place-items-center rounded-2xl gradient-hero text-white shadow-glow"><HeartPulse className="h-6 w-6" /></div><p className="mt-6 text-sm font-semibold uppercase tracking-[0.18em] text-primary">What MedVault solves</p><h2 className="mt-3 font-display text-3xl font-bold">Healthcare moves on documents. Privacy should move with them.</h2><p className="mt-4 max-w-2xl leading-7 text-muted-foreground">Teams often choose between slow manual redaction, disconnected tools, or risky sharing. MedVault brings detection, destructive redaction, review, quality assurance, audit evidence, and controlled delivery into a single workflow.</p></div></Card>
          <Card className="border-primary/20 bg-primary/5 p-7 sm:p-9"><Target className="h-8 w-8 text-primary" /><h2 className="mt-5 font-display text-2xl font-bold">Our goal</h2><p className="mt-3 leading-7 text-muted-foreground">Make privacy-safe data movement practical enough for everyday healthcare work—and rigorous enough for the moments when trust truly matters.</p><div className="mt-6 rounded-xl border border-primary/25 bg-background/70 p-4 text-sm"><span className="font-semibold text-primary">Aim:</span> accelerate responsible care, research, operations, and discovery without exposing the people behind the data.</div></Card>
        </div>
      </section>

      <section className="border-y bg-card/45 py-16"><div className="mx-auto max-w-6xl px-4 lg:px-8"><div className="max-w-3xl"><Badge variant="secondary">Compliance foundations</Badge><h2 className="mt-4 font-display text-3xl font-bold">Designed to support the controls that healthcare data deserves.</h2><p className="mt-3 leading-7 text-muted-foreground">MedVault is engineered to support privacy and security programs; compliance ultimately depends on an organisation’s deployment, policies, contracts, access governance, and legal assessment.</p></div><div className="mt-8 grid gap-4 md:grid-cols-2">{COMPLIANCE.map((item, index) => <motion.div key={item.title} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * 0.07 }}><Card className="h-full p-6 transition-all hover:border-primary/40 hover:shadow-glow"><item.icon className="h-7 w-7 text-primary" /><h3 className="mt-4 font-display text-lg font-semibold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p></Card></motion.div>)}</div></div></section>

      <section className="mx-auto max-w-6xl px-4 py-16 lg:px-8"><div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr]"><div><Badge variant="outline" className="border-primary/40">Security posture</Badge><h2 className="mt-4 font-display text-3xl font-bold">Security is a chain, not a checkbox.</h2><p className="mt-3 leading-7 text-muted-foreground">Every stage is designed to reduce exposure: from source handling and redaction rendering to QA, evidence, and controlled distribution.</p><div className="mt-7 rounded-2xl gradient-hero p-6 text-white"><Lock className="h-7 w-7" /><p className="mt-4 font-display text-xl font-semibold">Fail closed. Explain safely. Share deliberately.</p><p className="mt-2 text-sm leading-6 text-white/80">The system treats a privacy failure as a stop signal, not a warning users can casually bypass.</p></div></div><Card className="p-6 sm:p-8"><div className="space-y-4">{SECURITY.map((item) => <div key={item} className="flex gap-3"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><p className="text-sm leading-6 text-muted-foreground">{item}</p></div>)}</div></Card></div></section>

      <section className="border-y bg-primary/5 py-16"><div className="mx-auto max-w-6xl px-4 lg:px-8"><div className="text-center"><Badge variant="secondary">Why MedVault is different</Badge><h2 className="mt-4 font-display text-3xl font-bold">Utility, privacy, and proof—working together.</h2></div><div className="mt-9 grid gap-5 md:grid-cols-3">{DIFFERENTIATORS.map((item, index) => <motion.div key={item.title} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * 0.08 }}><Card className="h-full p-6"><div className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary"><item.icon className="h-6 w-6" /></div><h3 className="mt-5 font-display text-xl font-semibold">{item.title}</h3><p className="mt-3 text-sm leading-6 text-muted-foreground">{item.body}</p></Card></motion.div>)}</div></div></section>

      <section className="mx-auto max-w-5xl px-4 py-20 lg:px-8"><Card className="relative overflow-hidden border-primary/35 p-7 text-center shadow-elegant sm:p-12"><div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,hsla(var(--primary)/0.18),transparent_56%)]" /><div className="relative"><HeartPulse className="mx-auto h-10 w-10 text-primary animate-pulse-glow" /><p className="mx-auto mt-6 max-w-3xl font-display text-2xl font-bold leading-relaxed sm:text-4xl">“Privacy is not a barrier to progress. <span className="gradient-text">It is the foundation of trust in healthcare.</span>”</p><div className="mx-auto mt-9 grid max-w-3xl gap-3 text-left sm:grid-cols-2"><a href="mailto:vedantjain273@gmail.com" className="rounded-xl border bg-background/70 p-4 text-sm transition-colors hover:border-primary/50"><Mail className="mr-2 inline h-4 w-4 text-primary" />vedantjain273@gmail.com</a><a href="tel:+919829896609" className="rounded-xl border bg-background/70 p-4 text-sm transition-colors hover:border-primary/50"><Phone className="mr-2 inline h-4 w-4 text-primary" />+91 98298 96609</a></div><p className="mt-6 text-sm text-muted-foreground">Built by <span className="font-semibold text-foreground">Vedant Jain</span> to make healthcare data safer to use, share, and trust.</p></div></Card></section>
    </div>
  );
}
