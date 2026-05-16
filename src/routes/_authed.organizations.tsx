import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Building2, Plus } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth-context";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export const Route = createFileRoute("/_authed/organizations")({
  head: () => ({ meta: [{ title: "Organizations — Sentinel Net" }] }),
  component: OrgsPage,
});

interface Org { id: string; name: string; slug: string; created_at: string }

function OrgsPage() {
  const { isAdmin } = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const { data } = await supabase.from("organizations").select("*").order("created_at", { ascending: false });
    setOrgs((data as Org[]) ?? []);
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!name.trim() || !slug.trim()) return;
    setBusy(true);
    const { error } = await supabase.from("organizations").insert({ name: name.trim(), slug: slug.trim().toLowerCase() });
    setBusy(false);
    if (error) return toast.error(error.message);
    setName(""); setSlug("");
    toast.success("Organization created");
    load();
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary">TENANCY</p>
        <h1 className="text-3xl font-bold tracking-tight">Organizations</h1>
        <p className="text-sm text-muted-foreground">Top-level tenants. Departments and teams roll up here.</p>
      </div>

      {isAdmin && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold uppercase tracking-wider">New organization</h3>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <Input placeholder="Display name" value={name} onChange={(e) => setName(e.target.value)} />
            <Input placeholder="slug-name" value={slug} onChange={(e) => setSlug(e.target.value)} />
            <Button onClick={create} disabled={busy}>Create</Button>
          </div>
        </Card>
      )}

      <Card className="divide-y divide-border">
        {orgs.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">No organizations defined.</div>
        ) : orgs.map((o) => (
          <div key={o.id} className="flex items-center gap-4 p-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background/40 text-primary">
              <Building2 className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{o.name}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {o.slug} · created {new Date(o.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
