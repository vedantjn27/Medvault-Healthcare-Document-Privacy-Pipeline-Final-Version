import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { useActivity } from "@/lib/session/activity-store";
import { useAuth } from "@/lib/auth/auth-context";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PRIVACY_MODE_LABELS } from "@/lib/api/types";
import type { PrivacyMode } from "@/lib/api/types";
import {
  Upload,
  GitCompareArrows,
  Layers,
  ShieldAlert,
  Bell,
  FileText,
  Activity,
  ArrowRight,
  HardDrive,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { fmtDate } from "@/lib/format";
import { intelligenceApi } from "@/lib/api/client";

export const Route = createFileRoute("/app/")({
  component: DashboardPage,
});

const QUICK = [
  { to: "/app/upload", label: "Upload single doc", icon: Upload, hint: "Start the full workflow" },
  {
    to: "/app/compare",
    label: "Compare modes",
    icon: GitCompareArrows,
    hint: "Diff 2–5 standard modes",
  },
  { to: "/app/batch", label: "Batch redact", icon: Layers, hint: "Up to 25 files at once" },
  { to: "/app/audit", label: "Audit trail", icon: ShieldAlert, hint: "Verify integrity" },
];

function DashboardPage() {
  const { user } = useAuth();
  const { items } = useActivity();

  const docs = items.filter((i) => i.kind === "document");
  const jobs = items.filter((i) => i.kind === "job");
  const batches = items.filter((i) => i.kind === "batch");
  const sessionJobIds = jobs.map((job) => job.id).sort();
  const intelligenceQueries = useQueries({
    queries: sessionJobIds.map((jobId) => ({
      queryKey: ["intelligence", jobId],
      queryFn: () => intelligenceApi.job(jobId),
      retry: false,
    })),
  });
  const insights = intelligenceQueries
    .flatMap((query) => query.data ? [query.data] : [])
    .filter((insight) => insight.status === "complete" || insight.status === "qa_failed");
  const intelligence = {
    data: {
      completed_jobs: insights.length,
      qa_pass_rate: insights.length ? Math.round((insights.filter((insight) => insight.qa_passed).length / insights.length) * 100) : 0,
      review_approval_rate: insights.length ? Math.round((insights.filter((insight) => insight.review_status === "approved").length / insights.length) * 100) : 0,
      average_redactions: insights.length ? Math.round((insights.reduce((total, insight) => total + insight.redacted_count, 0) / insights.length) * 10) / 10 : 0,
    },
  };

  const modeCounts: Record<string, number> = {};
  jobs.forEach((j) => {
    if (j.privacyMode) modeCounts[j.privacyMode] = (modeCounts[j.privacyMode] ?? 0) + 1;
  });
  const chartData = Object.entries(modeCounts).map(([m, v]) => ({
    name: PRIVACY_MODE_LABELS[m as PrivacyMode] ?? m,
    value: v,
  }));
  const COLORS = [
    "var(--chart-1)",
    "var(--chart-2)",
    "var(--chart-3)",
    "var(--chart-4)",
    "var(--chart-5)",
  ];

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Badge variant="outline" className="mb-2">
          <Sparkles className="mr-1 h-3 w-3" /> Session-only history
        </Badge>
        <h1 className="font-display text-3xl font-bold">
          Welcome back{user ? `, ${user.email.split("@")[0]}` : ""}.
        </h1>
        <p className="mt-1 text-muted-foreground">
          Everything you touch this session lives here. It clears on logout.
        </p>
      </motion.div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={FileText}
          label="Documents this session"
          value={docs.length}
          accent="chart-1"
        />
        <StatCard icon={Activity} label="Redaction jobs" value={jobs.length} accent="chart-2" />
        <StatCard icon={Layers} label="Batch jobs" value={batches.length} accent="chart-3" />
        <StatCard
          icon={HardDrive}
          label="Downloaded this session"
          value={items.filter((i) => i.downloaded).length}
          accent="chart-4"
        />
      </div>

      {/* Quick actions + chart */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <h2 className="font-display text-lg font-semibold">Quick actions</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {QUICK.map((q, i) => (
              <motion.div
                key={q.to}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  to={q.to as "/app/upload"}
                  className="group flex items-center gap-3 rounded-xl border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-glow"
                >
                  <div className="grid h-11 w-11 place-items-center rounded-lg gradient-hero text-white">
                    <q.icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold">{q.label}</div>
                    <div className="truncate text-xs text-muted-foreground">{q.hint}</div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Link>
              </motion.div>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display text-lg font-semibold">Mode mix</h2>
          <p className="text-xs text-muted-foreground">Privacy modes used this session</p>
          <div className="mt-4 h-56">
            {chartData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    innerRadius={45}
                    outerRadius={80}
                    dataKey="value"
                    paddingAngle={4}
                  >
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="grid h-full place-items-center text-center text-xs text-muted-foreground">
                Run a redaction to see the mix.
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden border-primary/25">
        <div className="flex flex-wrap items-start justify-between gap-4 bg-primary/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-display text-lg font-semibold"><Sparkles className="h-5 w-5 text-primary" /> Privacy intelligence</div>
            <p className="mt-1 text-sm text-muted-foreground">Live compliance signals from safe metadata only — never document text or PHI.</p>
          </div>
          <Link to="/app/upload"><Button variant="outline" size="sm">Analyse a document <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
        </div>
        <div className="grid divide-y sm:grid-cols-4 sm:divide-x sm:divide-y-0">
          <InsightStat label="Completed jobs" value={intelligence.data?.completed_jobs ?? "—"} />
          <InsightStat label="QA pass rate" value={intelligence.data ? `${intelligence.data.qa_pass_rate}%` : "—"} />
          <InsightStat label="Review approvals" value={intelligence.data ? `${intelligence.data.review_approval_rate}%` : "—"} />
          <InsightStat label="Average redactions" value={intelligence.data?.average_redactions ?? "—"} />
        </div>
      </Card>

      {/* Recent */}
      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-semibold">Recent activity</h2>
          <Link to="/app/upload">
            <Button size="sm" variant="outline" className="gap-2">
              <Upload className="h-4 w-4" /> New upload
            </Button>
          </Link>
        </div>
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed py-12 text-center">
            <FileText className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Nothing yet. Upload a document to begin.
            </p>
            <Link to="/app/upload">
              <Button className="mt-4">Upload document</Button>
            </Link>
          </div>
        ) : (
          <ul className="divide-y">
            {items.slice(0, 12).map((item) => (
              <li key={`${item.kind}-${item.id}`} className="flex items-center gap-3 py-3">
                <Badge variant="outline" className="w-20 justify-center text-[10px] uppercase">
                  {item.kind}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{item.label ?? item.id}</div>
                  <div className="text-xs text-muted-foreground">
                    {fmtDate(new Date(item.createdAt).toISOString())}
                  </div>
                </div>
                {item.status ? <StatusBadge status={item.status} /> : null}
                {item.downloaded ? (
                  <Badge variant="secondary" className="text-[10px]">
                    Downloaded
                  </Badge>
                ) : null}
                {item.kind === "job" ? (
                  <Link to="/app/jobs/$jobId" params={{ jobId: item.id }}>
                    <Button variant="ghost" size="sm">
                      Open
                    </Button>
                  </Link>
                ) : item.kind === "document" ? (
                  <Link to="/app/documents/$documentId" params={{ documentId: item.id }}>
                    <Button variant="ghost" size="sm">
                      Open
                    </Button>
                  </Link>
                ) : (
                  <Link to="/app/batch/$batchId" params={{ batchId: item.id }}>
                    <Button variant="ghost" size="sm">
                      Open
                    </Button>
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="border-primary/30 bg-primary/5 p-6">
        <div className="flex items-start gap-4">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Bell className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-display text-base font-semibold">Enable browser notifications</h3>
            <p className="text-sm text-muted-foreground">
              Get notified the moment a redaction job finishes — without polling manually.
            </p>
          </div>
          <Link to="/app/settings">
            <Button variant="outline">Configure</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

function InsightStat({ label, value }: { label: string; value: string | number }) {
  return <div className="p-5"><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 font-display text-2xl font-bold text-primary">{value}</p></div>;
}

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <motion.div whileHover={{ y: -2 }}>
      <Card className="relative overflow-hidden p-5">
        <div
          className="absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-10 blur-xl"
          style={{ background: `var(--color-${accent})` }}
        />
        <div className="flex items-center gap-3">
          <div
            className="grid h-10 w-10 place-items-center rounded-lg"
            style={{
              background: `color-mix(in oklab, var(--color-${accent}) 20%, transparent)`,
              color: `var(--color-${accent})`,
            }}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <div className="font-display text-2xl font-bold">{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    queued: { cls: "bg-muted text-muted-foreground", label: "Queued" },
    processing: {
      cls: "bg-warning/20 text-warning-foreground border-warning/40",
      label: "Processing",
    },
    complete: { cls: "bg-success/20 text-success-foreground border-success/40", label: "Complete" },
    done: { cls: "bg-success/20 text-success-foreground border-success/40", label: "Done" },
    uploaded: { cls: "bg-primary/20 text-primary border-primary/40", label: "Uploaded" },
    qa_failed: {
      cls: "bg-destructive/20 text-destructive border-destructive/40",
      label: "QA failed",
    },
    error: { cls: "bg-destructive/20 text-destructive border-destructive/40", label: "Error" },
    expired: { cls: "bg-muted text-muted-foreground", label: "Expired" },
  };
  const s = map[status] ?? { cls: "bg-muted text-muted-foreground", label: status };
  return (
    <Badge variant="outline" className={`text-[10px] ${s.cls}`}>
      {s.label}
    </Badge>
  );
}
