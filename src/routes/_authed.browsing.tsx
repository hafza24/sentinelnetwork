import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Globe2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";

export const Route = createFileRoute("/_authed/browsing")({
  head: () => ({ meta: [{ title: "Browser History — Sentinel Net" }] }),
  component: BrowsingPage,
});

interface Row {
  id: string;
  browser: string | null;
  url: string;
  title: string | null;
  visited_at: string;
}

function BrowsingPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("browser_history")
        .select("id,browser,url,title,visited_at")
        .order("visited_at", { ascending: false })
        .limit(300);
      setRows((data as Row[]) ?? []);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">BROWSING</p>
        <h1 className="text-3xl font-bold tracking-tight">Browser history</h1>
        <p className="text-sm text-muted-foreground">Visited URLs reported by the agent's browser integration.</p>
      </div>
      <Card className="divide-y divide-border">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No browsing history yet.</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="flex items-start gap-4 p-4">
              <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
                <Globe2 className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{r.title ?? r.url}</p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">{r.url}</p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {r.browser ?? "browser"} · {new Date(r.visited_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
