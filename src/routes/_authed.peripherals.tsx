import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Camera, Mic } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/peripherals")({
  head: () => ({ meta: [{ title: "Camera & Microphone — Sentinel Net" }] }),
  component: PeripheralsPage,
});

interface Row {
  id: string;
  peripheral: "camera" | "microphone";
  app_name: string | null;
  state: string;
  occurred_at: string;
}

function PeripheralsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("peripheral_events")
        .select("id,peripheral,app_name,state,occurred_at")
        .order("occurred_at", { ascending: false })
        .limit(200);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">PERIPHERALS</p>
        <h1 className="text-3xl font-bold tracking-tight">Camera & Microphone access</h1>
        <p className="text-sm text-muted-foreground">Detect unauthorized activations and audit which apps requested device access.</p>
      </div>
      <Card className="divide-y divide-border">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No peripheral events recorded.</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="flex items-center gap-4 p-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
                {r.peripheral === "camera" ? <Camera className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{r.app_name ?? "Unknown app"}</p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {r.peripheral} · {new Date(r.occurred_at).toLocaleString()}
                </p>
              </div>
              <Badge variant={r.state === "blocked" ? "destructive" : r.state === "activated" ? "default" : "secondary"}>
                {r.state}
              </Badge>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
