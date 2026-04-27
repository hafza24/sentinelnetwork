-- screen_sessions
CREATE TABLE IF NOT EXISTS public.screen_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','stopped','error')),
  ws_endpoint TEXT,
  started_at TIMESTAMPTZ,
  stopped_at TIMESTAMPTZ,
  frame_count BIGINT NOT NULL DEFAULT 0,
  bytes_transferred BIGINT NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.screen_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins manage screen_sessions" ON public.screen_sessions;
CREATE POLICY "Admins manage screen_sessions" ON public.screen_sessions
  FOR ALL TO authenticated
  USING (public.has_role(auth.uid(),'admin'))
  WITH CHECK (public.has_role(auth.uid(),'admin'));

DROP POLICY IF EXISTS "Users read own screen_sessions" ON public.screen_sessions;
CREATE POLICY "Users read own screen_sessions" ON public.screen_sessions
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP TRIGGER IF EXISTS trg_screen_sessions_updated ON public.screen_sessions;
CREATE TRIGGER trg_screen_sessions_updated BEFORE UPDATE ON public.screen_sessions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_screen_sessions_device ON public.screen_sessions(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_screen_sessions_user ON public.screen_sessions(user_id, created_at DESC);

-- device_tasks
CREATE TABLE IF NOT EXISTS public.device_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  pid INT NOT NULL,
  process_name TEXT NOT NULL,
  cpu_percent NUMERIC(5,2),
  memory_mb NUMERIC(10,2),
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','killed','exited')),
  reported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.device_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins read all device_tasks" ON public.device_tasks;
CREATE POLICY "Admins read all device_tasks" ON public.device_tasks
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(),'admin'));

DROP POLICY IF EXISTS "Users read own device_tasks" ON public.device_tasks;
CREATE POLICY "Users read own device_tasks" ON public.device_tasks
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users insert own device_tasks" ON public.device_tasks;
CREATE POLICY "Users insert own device_tasks" ON public.device_tasks
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_device_tasks_device ON public.device_tasks(device_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_tasks_pid ON public.device_tasks(device_id, pid);

-- file_integrity
CREATE TABLE IF NOT EXISTS public.file_integrity (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID REFERENCES public.devices(id) ON DELETE CASCADE,
  user_id UUID,
  file_path TEXT NOT NULL,
  expected_sha256 TEXT NOT NULL,
  last_verified_at TIMESTAMPTZ,
  is_valid BOOLEAN NOT NULL DEFAULT TRUE,
  repair_count INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.file_integrity ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins read all file_integrity" ON public.file_integrity;
CREATE POLICY "Admins read all file_integrity" ON public.file_integrity
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(),'admin'));

DROP POLICY IF EXISTS "Users read own file_integrity" ON public.file_integrity;
CREATE POLICY "Users read own file_integrity" ON public.file_integrity
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users insert own file_integrity" ON public.file_integrity;
CREATE POLICY "Users insert own file_integrity" ON public.file_integrity
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_file_integrity_device ON public.file_integrity(device_id);

-- Realtime
ALTER TABLE public.screen_sessions REPLICA IDENTITY FULL;
ALTER TABLE public.device_tasks REPLICA IDENTITY FULL;
ALTER TABLE public.file_integrity REPLICA IDENTITY FULL;

DO $$ BEGIN
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.screen_sessions; EXCEPTION WHEN duplicate_object THEN NULL; END;
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.device_tasks; EXCEPTION WHEN duplicate_object THEN NULL; END;
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.file_integrity; EXCEPTION WHEN duplicate_object THEN NULL; END;
END $$;

-- Add screenshot_bucket / screenshot_storage_path to activity_events if missing
ALTER TABLE public.activity_events
  ADD COLUMN IF NOT EXISTS screenshot_bucket TEXT DEFAULT 'violation-screenshots',
  ADD COLUMN IF NOT EXISTS screenshot_storage_path TEXT;