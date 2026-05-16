import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/files")({
  head: () => ({ meta: [{ title: "File Activity — Sentinel Net" }] }),
  component: FilesPage,
});

interface Row {
  id: string;
  action: string;
  file_path: string;
  size_bytes: number | null;
  destination: string | null;
  occurred_at: string;
}

function fmtBytes(n: number | null) {
  if (!n) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${u[i]}`;
}

function FilesPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("file_events")
        .select("id,action,file_path,size_bytes,destination,occurred_at")
        .order("occurred_at", { ascending: false })
        .limit(200);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">FILE ACTIVITY</p>
        <h1 className="text-3xl font-bold tracking-tight">Sensitive file movement</h1>
        <p className="text-sm text-muted-foreground">Monitor copies, deletions, and cloud uploads across managed endpoints.</p>
      </div>
      <Card className="divide-y divide-border">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No file events recorded.</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="flex items-center gap-4 p-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-xs text-foreground">{r.file_path}</p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {fmtBytes(r.size_bytes)}
                  {r.destination ? ` → ${r.destination}` : ""} · {new Date(r.occurred_at).toLocaleString()}
                </p>
              </div>
              <Badge variant={r.action === "deleted" || r.action === "uploaded" ? "destructive" : "secondary"}>
                {r.action}
              </Badge>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
