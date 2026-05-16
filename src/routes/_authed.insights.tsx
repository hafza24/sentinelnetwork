import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/insights")({
  head: () => ({ meta: [{ title: "AI Insights — Sentinel Net" }] }),
  component: InsightsPage,
});

interface Row {
  id: string;
  category: string;
  title: string;
  summary: string;
  severity: string;
  created_at: string;
}

function InsightsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("ai_insights")
        .select("id,category,title,summary,severity,created_at")
        .order("created_at", { ascending: false })
        .limit(100);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">AI ANALYTICS</p>
        <h1 className="text-3xl font-bold tracking-tight">Insights &amp; recommendations</h1>
        <p className="text-sm text-muted-foreground">Anomaly detection, threat scoring, and productivity intelligence.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {loading ? (
          <Card className="p-6 text-sm text-muted-foreground">Loading…</Card>
        ) : rows.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">No insights generated yet.</Card>
        ) : (
          rows.map((r) => (
            <Card key={r.id} className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    {r.category}
                  </span>
                </div>
                <Badge variant={r.severity === "critical" ? "destructive" : r.severity === "warning" ? "default" : "secondary"}>
                  {r.severity}
                </Badge>
              </div>
              <h3 className="text-base font-semibold">{r.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{r.summary}</p>
              <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {new Date(r.created_at).toLocaleString()}
              </p>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
