
-- Organizations & departments
CREATE TABLE IF NOT EXISTS public.organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read organizations" ON public.organizations FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins manage organizations" ON public.organizations FOR ALL TO authenticated USING (has_role(auth.uid(),'admin')) WITH CHECK (has_role(auth.uid(),'admin'));

CREATE TABLE IF NOT EXISTS public.departments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read departments" ON public.departments FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins manage departments" ON public.departments FOR ALL TO authenticated USING (has_role(auth.uid(),'admin')) WITH CHECK (has_role(auth.uid(),'admin'));

-- USB events
CREATE TABLE IF NOT EXISTS public.usb_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID,
  user_id UUID NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('inserted','removed','blocked','readonly')),
  vendor TEXT,
  product TEXT,
  serial TEXT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.usb_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own usb_events" ON public.usb_events FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Admins read all usb_events" ON public.usb_events FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Users insert own usb_events" ON public.usb_events FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Peripheral (camera/mic) events
CREATE TABLE IF NOT EXISTS public.peripheral_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID,
  user_id UUID NOT NULL,
  peripheral TEXT NOT NULL CHECK (peripheral IN ('camera','microphone')),
  app_name TEXT,
  state TEXT NOT NULL CHECK (state IN ('activated','deactivated','blocked')),
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.peripheral_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own peripheral_events" ON public.peripheral_events FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Admins read all peripheral_events" ON public.peripheral_events FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Users insert own peripheral_events" ON public.peripheral_events FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- File events
CREATE TABLE IF NOT EXISTS public.file_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID,
  user_id UUID NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('created','modified','deleted','copied','moved','uploaded')),
  file_path TEXT NOT NULL,
  size_bytes BIGINT,
  destination TEXT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.file_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own file_events" ON public.file_events FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Admins read all file_events" ON public.file_events FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Users insert own file_events" ON public.file_events FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Browser history
CREATE TABLE IF NOT EXISTS public.browser_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID,
  user_id UUID NOT NULL,
  browser TEXT,
  url TEXT NOT NULL,
  title TEXT,
  visited_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.browser_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own browser_history" ON public.browser_history FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Admins read all browser_history" ON public.browser_history FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Users insert own browser_history" ON public.browser_history FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Audit logs (append-only)
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Admins read audit_logs" ON public.audit_logs FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Authenticated insert audit_logs" ON public.audit_logs FOR INSERT TO authenticated WITH CHECK (auth.uid() = actor_id);

-- AI insights
CREATE TABLE IF NOT EXISTS public.ai_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category TEXT NOT NULL CHECK (category IN ('anomaly','productivity','threat','recommendation','burnout')),
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  severity alert_severity NOT NULL DEFAULT 'info',
  device_id UUID,
  user_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.ai_insights ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Admins read all ai_insights" ON public.ai_insights FOR SELECT TO authenticated USING (has_role(auth.uid(),'admin'));
CREATE POLICY "Users read own ai_insights" ON public.ai_insights FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Admins manage ai_insights" ON public.ai_insights FOR ALL TO authenticated USING (has_role(auth.uid(),'admin')) WITH CHECK (has_role(auth.uid(),'admin'));

CREATE INDEX IF NOT EXISTS idx_usb_events_user ON public.usb_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_peripheral_events_user ON public.peripheral_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_file_events_user ON public.file_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_browser_history_user ON public.browser_history(user_id, visited_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_insights_created ON public.ai_insights(created_at DESC);
