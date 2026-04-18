import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export const Route = createFileRoute("/_authed/alerts")({
  head: () => ({
    meta: [
      { title: "Alerts — Sentinel Net" },
      { name: "description", content: "Real-time security event log from agents in the field." },
    ],
  }),
  component: AlertsPage,
});

interface Alert {
  id: string;
  device_id: string | null;
  user_id: string | null;
  action_type: string;
  target: string | null;
  severity: "info" | "warning" | "critical";
  metadata: Record<string, unknown> | null;
  created_at: string;
}

const SEVERITY_STYLES = {
  info: "bg-info/15 text-info border-info/30",
  warning: "bg-warning/15 text-warning border-warning/30",
  critical: "bg-destructive/15 text-destructive border-destructive/30",
};

function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data, error } = await supabase
        .from("alerts")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(200);
      if (error) toast.error(error.message);
      else setAlerts((data as Alert[]) ?? []);
      setLoading(false);
    })();

    const channel = supabase
      .channel("alerts-stream")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "alerts" },
        (payload) => {
          const next = payload.new as Alert;
          setAlerts((prev) => [next, ...prev].slice(0, 200));
          if (next.severity === "critical") {
            toast.error(`Critical: ${next.action_type}${next.target ? ` → ${next.target}` : ""}`);
          } else if (next.severity === "warning") {
            toast.warning(`${next.action_type}${next.target ? ` → ${next.target}` : ""}`);
          }
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">EVENTS</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">Alerts</h1>
        <p className="text-sm text-muted-foreground">
          Security events captured by Sentinel agents.
        </p>
      </div>

      {loading ? (
        <Card className="flex items-center justify-center p-10">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </Card>
      ) : alerts.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 p-10 text-center">
          <AlertTriangle className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No alerts yet. The grid is quiet.</p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="divide-y divide-border">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-start gap-4 p-4">
                <Badge
                  variant="outline"
                  className={`shrink-0 font-mono text-[10px] uppercase ${SEVERITY_STYLES[a.severity]}`}
                >
                  {a.severity}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{a.action_type}</p>
                  {a.target && (
                    <p className="font-mono text-xs text-muted-foreground">→ {a.target}</p>
                  )}
                </div>
                <p className="shrink-0 font-mono text-[11px] text-muted-foreground">
                  {new Date(a.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
