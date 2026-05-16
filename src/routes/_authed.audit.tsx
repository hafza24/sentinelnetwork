import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/audit")({
  head: () => ({ meta: [{ title: "Audit Log — Sentinel Net" }] }),
  component: AuditPage,
});

interface Row {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  created_at: string;
}

function AuditPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("audit_logs")
        .select("id,actor_id,action,target_type,target_id,created_at")
        .order("created_at", { ascending: false })
        .limit(300);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">AUDIT</p>
        <h1 className="text-3xl font-bold tracking-tight">Administrator audit log</h1>
        <p className="text-sm text-muted-foreground">Append-only record of privileged actions performed in the console.</p>
      </div>
      <Card className="divide-y divide-border">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No audit events yet.</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="flex items-center gap-4 p-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
                <ScrollText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{r.action}</p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {r.target_type ?? "system"}
                  {r.target_id ? ` · ${r.target_id}` : ""} · {new Date(r.created_at).toLocaleString()}
                </p>
              </div>
              <Badge variant="secondary" className="font-mono text-[10px]">
                {(r.actor_id ?? "system").slice(0, 8)}
              </Badge>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
