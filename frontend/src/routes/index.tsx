import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import {
  ShieldCheck,
  Sparkles,
  Layers,
  GitCompareArrows,
  Bell,
  FileSearch,
  Lock,
  Zap,
  HeartPulse,
  ArrowRight,
  CheckCircle2,
  Users,
  Stethoscope,
  Github,
  Mail,
  Linkedin,
  Phone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/auth/auth-context";
import heroImg from "@/assets/branding-hero.jpg";
import heroLightImg from "@/assets/branding-hero-light.png";
import waveImg from "@/assets/branding-section.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MedVault — Healthcare Document Privacy Pipeline" },
      {
        name: "description",
        content:
          "Automated PHI redaction for PDFs, DICOM, DOCX, XLSX, images, emails and mailboxes. Privacy modes, QA gates, tamper-evident audit trails, and secure session exports.",
      },
    ],
  }),
  component: BrandingPage,
});

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "5 privacy modes",
    body: "Patient Portal, Research Sharing, Insurance Processing, Legal Discovery, and fully Custom rules.",
  },
  {
    icon: FileSearch,
    title: "Explainable detections",
    body: "Per-entity confidence, detector sources, page bounding boxes and privileged-flag semantics.",
  },
  {
    icon: Layers,
    title: "9 file types + embedded images",
    body: "PDF, DOCX, XLSX, JPEG, PNG, TIFF, DICOM, EML, MBOX — with faces, barcodes and OCR.",
  },
  {
    icon: GitCompareArrows,
    title: "Mode comparison",
    body: "Run two to five standard modes against one document and see redaction diffs by category.",
  },
  {
    icon: Lock,
    title: "QA fails closed",
    body: "Residual sensitive data blocks export. No override. Ever.",
  },
  {
    icon: Bell,
    title: "Verifiable audit chain",
    body: "Hash-linked events for every action. Verify integrity with a single click.",
  },
];

const MODES = [
  { name: "Patient Portal", tone: "Preserves subject identifier + dates.", color: "chart-1" },
  { name: "Research Sharing", tone: "Synthetic replacements + risk analysis.", color: "chart-2" },
  { name: "Insurance Processing", tone: "Keeps claim codes, NPI, payer fields.", color: "chart-3" },
  { name: "Legal Discovery", tone: "Max redaction + privilege flags.", color: "chart-4" },
  { name: "Custom", tone: "Pick categories, confidence, replacement.", color: "chart-5" },
];

const HERO_PARTICLES = [
  [8, 22, 3, 0], [14, 68, 2, 1.1], [20, 38, 4, 2.5], [27, 81, 2, 0.4],
  [34, 15, 3, 3.2], [41, 75, 2, 1.8], [52, 21, 3, 0.8], [59, 83, 4, 2.9],
  [66, 32, 2, 1.4], [72, 62, 3, 0.2], [78, 17, 2, 2.1], [84, 77, 4, 1.6],
  [91, 42, 2, 3.5], [94, 64, 3, 0.6],
] as const;

function HeroParticles() {
  return (
    <div className="hero-particles" aria-hidden="true">
      {HERO_PARTICLES.map(([left, top, size, delay], index) => (
        <span
          key={index}
          className="hero-particle"
          style={{
            left: `${left}%`,
            top: `${top}%`,
            width: `${size * 3}px`,
            height: `${size * 3}px`,
            animationDelay: `${delay}s`,
          }}
        />
      ))}
    </div>
  );
}

function BrandingPage() {
  const auth = useAuth();
  const authed = auth.status === "authenticated";

  return (
    <div className="relative overflow-x-hidden bg-background">
      {/* NAV */}
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border/40 bg-background/70 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-6 md:flex">
            <a href="#features" className="text-sm text-muted-foreground hover:text-foreground">
              Features
            </a>
            <a href="#modes" className="text-sm text-muted-foreground hover:text-foreground">
              Privacy Modes
            </a>
            <a href="#workflow" className="text-sm text-muted-foreground hover:text-foreground">
              Workflow
            </a>
            <a href="#trust" className="text-sm text-muted-foreground hover:text-foreground">
              Trust
            </a>
            <Link to="/about" className="text-sm text-muted-foreground hover:text-foreground">
              About
            </Link>
            <a href="#contact" className="text-sm text-muted-foreground hover:text-foreground">
              Contact
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {authed ? (
              <Link to="/app">
                <Button size="sm">Open app</Button>
              </Link>
            ) : (
              <>
                <Link to="/auth/login">
                  <Button variant="ghost" size="sm">
                    Log in
                  </Button>
                </Link>
                <Link to="/auth/register">
                  <Button size="sm">Get started</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="branding-hero relative flex min-h-screen items-center justify-center overflow-hidden pt-16">
        <img
          src={heroImg}
          alt=""
          aria-hidden
          className="branding-hero-image branding-hero-image-dark absolute inset-0 h-full w-full object-cover"
          width={1600}
          height={1000}
        />
        <img
          src={heroLightImg}
          alt=""
          aria-hidden
          className="branding-hero-image branding-hero-image-light absolute inset-0 h-full w-full object-cover"
          width={1600}
          height={1000}
        />
        <div className="branding-hero-overlay absolute inset-0" />
        <div className="absolute inset-0 grid-pattern opacity-30" />
        <div className="hero-orbit hero-orbit-one" aria-hidden="true" />
        <div className="hero-orbit hero-orbit-two" aria-hidden="true" />
        <HeroParticles />

        <div className="relative z-10 mx-auto max-w-6xl px-4 py-24 text-center lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Badge
              variant="outline"
              className="mb-6 border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium"
            >
              <Sparkles className="mr-1.5 h-3 w-3" />
              Healthcare Document Privacy Pipeline
            </Badge>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="hero-headline mx-auto max-w-5xl font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl"
          >
            Redact clinical documents
            <br />
            <span className="gradient-text">without losing their meaning.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg"
          >
            MedVault removes PHI from PDFs, DICOM, spreadsheets, images and emails with five privacy
            modes, explainable detections, tamper-evident audit chains and secure session exports.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="mt-10 flex flex-wrap items-center justify-center gap-3"
          >
            {authed ? (
              <Link to="/app">
                <Button size="lg" className="gap-2 shadow-glow">
                  Open MedVault <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/auth/register">
                  <Button size="lg" className="gap-2 shadow-glow">
                    Start free — create account <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link to="/auth/login">
                  <Button size="lg" variant="outline">
                    Sign in
                  </Button>
                </Link>
              </>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs text-muted-foreground"
          >
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Temporary storage only
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> QA fails closed
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Repeat session downloads
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Hash-chained audit
            </span>
          </motion.div>
        </div>

        {/* Floating vault glow */}
        <motion.div
          animate={{ y: [0, -20, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          className="pointer-events-none absolute bottom-10 right-10 hidden h-32 w-32 lg:block"
        >
          <div className="absolute inset-0 animate-pulse-glow rounded-full gradient-hero opacity-60 blur-2xl" />
        </motion.div>
      </section>

      {/* IMPACT LINE */}
      <section className="relative border-y bg-gradient-to-r from-transparent via-primary/5 to-transparent py-20">
        <motion.blockquote
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto max-w-4xl px-4 text-center"
        >
          <HeartPulse className="mx-auto mb-6 h-10 w-10 text-primary animate-pulse-glow" />
          <p className="font-display text-2xl font-medium leading-relaxed tracking-tight sm:text-3xl lg:text-4xl">
            &ldquo;Privacy is not a barrier to progress.
            <br />
            <span className="gradient-text">It is the foundation of trust in healthcare.</span>
            &rdquo;
          </p>
        </motion.blockquote>
      </section>

      {/* STATS */}
      <section className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[
            { n: "40+", l: "Entity categories detected" },
            { n: "9", l: "File formats supported" },
            { n: "5", l: "Configurable privacy modes" },
            { n: "≤2s", l: "Job status poll cadence" },
          ].map((s, i) => (
            <motion.div
              key={s.l}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
            >
              <Card className="border-primary/20 bg-card/50 p-6 backdrop-blur">
                <div className="gradient-text font-display text-4xl font-bold">{s.n}</div>
                <div className="mt-2 text-xs text-muted-foreground">{s.l}</div>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="mx-auto max-w-7xl px-4 py-24 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <Badge variant="outline" className="mb-4">
            Capabilities
          </Badge>
          <h2 className="font-display text-3xl font-bold sm:text-5xl">
            Every clinical document. Every category. Every audit event.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Built to make PHI removal deterministic, explainable and inspectable.
          </p>
        </div>
        <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
            >
              <Card className="group relative h-full overflow-hidden border-border/50 bg-card p-6 transition-all hover:border-primary/40 hover:shadow-glow">
                <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl gradient-hero shadow-glow">
                  <f.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="font-display text-lg font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
                <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/5 opacity-0 blur-2xl transition-opacity group-hover:opacity-100" />
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* MODES */}
      <section id="modes" className="relative overflow-hidden py-24">
        <img
          src={waveImg}
          alt=""
          aria-hidden
          width={1600}
          height={900}
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover opacity-20"
        />
        <div className="absolute inset-0 bg-background/70" />
        <div className="relative mx-auto max-w-7xl px-4 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <Badge variant="outline" className="mb-4">
              Privacy Modes
            </Badge>
            <h2 className="font-display text-3xl font-bold sm:text-5xl">
              One document. Multiple lenses.
            </h2>
            <p className="mt-4 text-muted-foreground">
              Compare two to five standard modes and see exactly which entities each preserves or
              removes.
            </p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            {MODES.map((m, i) => (
              <motion.div
                key={m.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
              >
                <Card className="glass h-full p-5">
                  <div
                    className={`h-1.5 w-10 rounded-full`}
                    style={{ background: `var(--color-${m.color})` }}
                  />
                  <h3 className="mt-4 font-display font-semibold">{m.name}</h3>
                  <p className="mt-2 text-xs text-muted-foreground">{m.tone}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* WORKFLOW */}
      <section id="workflow" className="mx-auto max-w-7xl px-4 py-24 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <Badge variant="outline" className="mb-4">
            Workflow
          </Badge>
          <h2 className="font-display text-3xl font-bold sm:text-5xl">
            From upload to export, in nine deliberate steps.
          </h2>
        </div>
        <ol className="mx-auto mt-14 grid max-w-4xl gap-4">
          {[
            "Upload — 9 formats, up to 50 MiB, ephemeral by design.",
            "Preview — auth-gated, marked pre-redaction, never persisted.",
            "Configure — choose a privacy mode or write custom rules.",
            "Run — job is queued; status polled every two seconds.",
            "Report — filter entities, sort by confidence, inspect explanations.",
            "Heatmap — SVG overlay of redaction coordinates & intensity.",
            "Feedback — mark correct, false positive, or missed items.",
            "Audit — verify the hash chain end-to-end.",
            "Export — download additional copies while the authenticated session remains valid.",
          ].map((step, i) => (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="flex items-start gap-4 rounded-xl border bg-card/50 p-4"
            >
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full gradient-hero text-sm font-bold text-white">
                {i + 1}
              </div>
              <p className="pt-1 text-sm">{step}</p>
            </motion.li>
          ))}
        </ol>
      </section>

      {/* TRUST */}
      <section id="trust" className="border-y bg-muted/20 py-24">
        <div className="mx-auto max-w-6xl px-4 lg:px-8">
          <div className="grid gap-8 md:grid-cols-3">
            {[
              {
                icon: Zap,
                title: "QA gate fails closed",
                body: "Residual PHI blocks export. There is no override. If QA fails, you see the report — never the file.",
              },
              {
                icon: Lock,
                title: "Ephemeral by design",
                body: "Source and output bytes live only in temporary storage and are removed by TTL cleanup. Browser state clears on logout.",
              },
              {
                icon: Users,
                title: "Feedback stays private",
                body: "Correct, false positive and missed flags calibrate future confidence — no raw PHI is ever attached.",
              },
            ].map((t) => (
              <Card key={t.title} className="border-primary/20 bg-card/60 p-6 backdrop-blur">
                <t.icon className="h-8 w-8 text-primary" />
                <h3 className="mt-4 font-display text-lg font-semibold">{t.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{t.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="branding-cta relative overflow-hidden py-24">
        <iframe
          src="https://my.spline.design/pillanddnaanimation-b1YSxlGPeJiBxVp9nawkci00/"
          title="Decorative pill and DNA animation"
          className="spline-cta-background"
          allow="autoplay; fullscreen"
          loading="lazy"
          tabIndex={-1}
          aria-hidden="true"
        />
        <div className="spline-cta-overlay absolute inset-0" />
        <div className="relative z-10 mx-auto max-w-3xl px-4 text-center lg:px-8">
          <Stethoscope className="mx-auto mb-6 h-10 w-10 text-primary" />
          <h2 className="font-display text-3xl font-bold sm:text-5xl">
            Move faster, without compromising anyone.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Create an account, upload a document, and watch a privacy-safe copy emerge — with a full
            audit trail.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {authed ? (
              <Link to="/app">
                <Button size="lg" className="gap-2 shadow-glow">
                  Open app <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            ) : (
              <Link to="/auth/register">
                <Button size="lg" className="gap-2 shadow-glow">
                  Create your account <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* CONTACT / FOOTER */}
      <footer id="contact" className="border-t bg-card/40 py-16">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 md:grid-cols-3 lg:px-8">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              A healthcare document privacy pipeline. Built with clinical rigor and open standards.
            </p>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold">Contact & Help</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                <a href="mailto:vedantjain273@gmail.com" className="hover:text-foreground">
                  vedantjain273@gmail.com
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4" />
                <a href="tel:+919829896609" className="hover:text-foreground">
                  +91 98298 96609
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Linkedin className="h-4 w-4" />
                <a
                  href="https://www.linkedin.com/in/vedant-jain-858348318"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-foreground"
                >
                  linkedin.com/in/vedant-jain-858348318
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Github className="h-4 w-4" />
                <span>MedVault backend on FastAPI</span>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold">Product</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>
                <a href="#features" className="hover:text-foreground">
                  Features
                </a>
              </li>
              <li>
                <a href="#modes" className="hover:text-foreground">
                  Privacy modes
                </a>
              </li>
              <li>
                <a href="#workflow" className="hover:text-foreground">
                  Workflow
                </a>
              </li>
              <li>
                {authed ? (
                  <Link to="/app" className="hover:text-foreground">
                    Open app
                  </Link>
                ) : (
                  <Link to="/auth/login" className="hover:text-foreground">
                    Sign in
                  </Link>
                )}
              </li>
            </ul>
          </div>
        </div>
        <div className="mx-auto mt-12 max-w-7xl border-t px-4 pt-6 text-center text-xs text-muted-foreground lg:px-8">
          © {new Date().getFullYear()} MedVault. Privacy is the foundation of trust in healthcare.
        </div>
      </footer>
    </div>
  );
}
