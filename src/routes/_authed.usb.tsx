import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Usb } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/usb")({
  head: () => ({ meta: [{ title: "USB Activity — Sentinel Net" }] }),
  component: UsbPage,
});

interface Row {
  id: string;
  event_type: string;
  vendor: string | null;
  product: string | null;
  serial: string | null;
  occurred_at: string;
}

function UsbPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("usb_events")
        .select("id,event_type,vendor,product,serial,occurred_at")
        .order("occurred_at", { ascending: false })
        .limit(200);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">USB &amp; REMOVABLE MEDIA</p>
        <h1 className="text-3xl font-bold tracking-tight">USB device activity</h1>
        <p className="text-sm text-muted-foreground">Track insertions, removals, and blocked removable storage events.</p>
      </div>
      <Card className="divide-y divide-border">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No USB events recorded.</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="flex items-center gap-4 p-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
                <Usb className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {[r.vendor, r.product].filter(Boolean).join(" ") || "Unknown device"}
                </p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {r.serial ?? "no serial"} · {new Date(r.occurred_at).toLocaleString()}
                </p>
              </div>
              <Badge variant={r.event_type === "blocked" ? "destructive" : "secondary"}>{r.event_type}</Badge>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
