import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { MonitorPlay, Maximize2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authed/live-stream")({
  head: () => ({ meta: [{ title: "Live Stream — Sentinel Net" }] }),
  component: LiveStreamPage,
});

interface Session {
  id: string;
  device_id: string;
  status: string;
  ws_endpoint: string | null;
  frame_count: number;
  bytes_transferred: number;
  started_at: string | null;
}

function LiveStreamPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const { data } = await supabase
        .from("screen_sessions")
        .select("id,device_id,status,ws_endpoint,frame_count,bytes_transferred,started_at")
        .order("created_at", { ascending: false })
        .limit(20);
      setSessions((data as Session[]) ?? []);
      setLoading(false);
    };
    load();
    const ch = supabase
      .channel("screen-sessions-live")
      .on("postgres_changes", { event: "*", schema: "public", table: "screen_sessions" }, load)
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, []);

  const active = sessions.filter((s) => s.status === "active" || s.status === "streaming");

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">LIVE STREAM</p>
        <h1 className="text-3xl font-bold tracking-tight">Realtime desktop viewer</h1>
        <p className="text-sm text-muted-foreground">WebRTC / WebSocket signaled screen streams from active endpoints.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {loading ? (
          <Card className="p-6 text-sm text-muted-foreground">Loading…</Card>
        ) : active.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">No active streams. Issue a <code className="font-mono">start_stream</code> command from Remote Control.</Card>
        ) : (
          active.map((s) => (
            <Card key={s.id} className="overflow-hidden">
              <div className="relative flex aspect-video items-center justify-center bg-background/60">
                <MonitorPlay className="h-12 w-12 text-muted-foreground" />
                <Badge className="absolute left-3 top-3 bg-destructive/90">LIVE</Badge>
                <button className="absolute right-3 top-3 rounded-md border border-border bg-background/60 p-1.5 text-muted-foreground hover:text-foreground">
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="border-t border-border p-4">
                <p className="truncate font-mono text-[11px] text-muted-foreground">{s.device_id}</p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {s.frame_count} frames · {(s.bytes_transferred / 1024).toFixed(1)} KB
                </p>
              </div>
            </Card>
          ))
        )}
      </div>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider">Recent sessions</h3>
        <div className="divide-y divide-border">
          {sessions.length === 0 ? (
            <div className="py-3 text-sm text-muted-foreground">No sessions yet.</div>
          ) : sessions.map((s) => (
            <div key={s.id} className="flex items-center gap-3 py-3">
              <span className="font-mono text-[11px] text-muted-foreground">{s.device_id.slice(0, 8)}</span>
              <span className="flex-1 truncate text-sm">{s.ws_endpoint ?? "—"}</span>
              <Badge variant={s.status === "active" ? "default" : "secondary"}>{s.status}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
