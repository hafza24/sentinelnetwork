import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, Download, ShieldAlert, Activity, Cpu } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/reports")({
  head: () => ({
    meta: [
      { title: "Analytics & Reports — Sentinel Net" },
      {
        name: "description",
        content:
          "Productivity, security, and threat analytics across the Sentinel Net fleet.",
      },
    ],
  }),
  component: ReportsPage,
});

interface AlertRow {
  id: string;
  severity: "info" | "warning" | "critical" | string;
  action_type: string | null;
  created_at: string;
}
interface ActivityRow {
  id: string;
  event_type: string | null;
  occurred_at: string;
}
interface DeviceRow {
  id: string;
  status: string;
  os: string | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "hsl(var(--destructive))",
  warning: "hsl(38 92% 50%)",
  info: "hsl(var(--primary))",
};

function ReportsPage() {
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const since = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString();
      const [a, ev, d] = await Promise.all([
        supabase
          .from("alerts")
          .select("id,severity,action_type,created_at")
          .gte("created_at", since)
          .order("created_at", { ascending: true })
          .limit(1000),
        supabase
          .from("activity_events")
          .select("id,event_type,occurred_at")
          .gte("occurred_at", since)
          .order("occurred_at", { ascending: true })
          .limit(2000),
        supabase.from("devices").select("id,status,os").limit(500),
      ]);
      setAlerts((a.data as AlertRow[]) ?? []);
      setActivity((ev.data as ActivityRow[]) ?? []);
      setDevices((d.data as DeviceRow[]) ?? []);
      setLoading(false);
    })();
  }, []);

  // Trend by day
  const trend = useMemo(() => {
    const buckets = new Map<string, { day: string; alerts: number; events: number }>();
    const seed = (ts: string) => {
      const day = ts.slice(0, 10);
      if (!buckets.has(day)) buckets.set(day, { day, alerts: 0, events: 0 });
      return buckets.get(day)!;
    };
    alerts.forEach((r) => seed(r.created_at).alerts++);
    activity.forEach((r) => seed(r.occurred_at).events++);
    return Array.from(buckets.values()).sort((a, b) => a.day.localeCompare(b.day));
  }, [alerts, activity]);

  const severityMix = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, warning: 0, info: 0 };
    alerts.forEach((a) => {
      counts[a.severity] = (counts[a.severity] ?? 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [alerts]);

  const topActions = useMemo(() => {
    const c = new Map<string, number>();
    alerts.forEach((a) => {
      const k = a.action_type ?? "unknown";
      c.set(k, (c.get(k) ?? 0) + 1);
    });
    return Array.from(c.entries())
      .map(([action, count]) => ({ action, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [alerts]);

  const fleetByOs = useMemo(() => {
    const c = new Map<string, number>();
    devices.forEach((d) => {
      const k = (d.os ?? "Unknown").split(" ")[0];
      c.set(k, (c.get(k) ?? 0) + 1);
    });
    return Array.from(c.entries()).map(([os, count]) => ({ os, count }));
  }, [devices]);

  const exportCsv = () => {
    const rows = [
      ["day", "alerts", "events"],
      ...trend.map((t) => [t.day, t.alerts, t.events]),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sentinel-report-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const critical = alerts.filter((a) => a.severity === "critical").length;
  const online = devices.filter((d) => d.status === "active").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">
            INTELLIGENCE · 14-DAY WINDOW
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Analytics & Reports</h1>
          <p className="text-sm text-muted-foreground">
            Productivity, security posture, and threat trends across the fleet.
          </p>
        </div>
        <Button variant="outline" onClick={exportCsv} disabled={loading || !trend.length}>
          <Download className="mr-2 h-4 w-4" /> Export CSV
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={Activity} label="Activity events" value={activity.length} hint="last 14d" />
        <Stat icon={ShieldAlert} label="Alerts" value={alerts.length} hint="last 14d" />
        <Stat
          icon={ShieldAlert}
          label="Critical"
          value={critical}
          hint="severity = critical"
          tone="critical"
        />
        <Stat icon={Cpu} label="Online devices" value={online} hint={`${devices.length} total`} />
      </div>

      <Card className="p-5">
        <SectionHeader title="Alerts & activity trend" icon={BarChart3} />
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend}>
              <defs>
                <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--destructive))" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="events"
                stroke="hsl(var(--primary))"
                fill="url(#ga)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="alerts"
                stroke="hsl(var(--destructive))"
                fill="url(#gb)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeader title="Severity mix" icon={ShieldAlert} />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severityMix}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={90}
                  innerRadius={50}
                  paddingAngle={2}
                >
                  {severityMix.map((s) => (
                    <Cell key={s.name} fill={SEVERITY_COLORS[s.name] ?? "hsl(var(--muted))"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeader title="Top enforcement actions" icon={Activity} />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topActions} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis
                  type="category"
                  dataKey="action"
                  width={120}
                  tick={{ fontSize: 11 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeader title="Fleet composition by OS" icon={Cpu} />
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={fleetByOs}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="os" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  hint: string;
  tone?: "critical";
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            {hint}
          </p>
          <p
            className={`mt-2 text-3xl font-bold ${tone === "critical" ? "text-destructive" : "text-foreground"}`}
          >
            {value.toLocaleString()}
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">{label}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/50 text-primary">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </Card>
  );
}

function SectionHeader({ title, icon: Icon }: { title: string; icon: typeof Activity }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">{title}</h3>
      </div>
      <Badge variant="secondary" className="font-mono text-[10px]">
        LIVE
      </Badge>
    </div>
  );
}
