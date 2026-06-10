CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id text PRIMARY KEY,
  pipeline_name text NOT NULL,
  pipeline_version text NOT NULL,
  execution_mode text NOT NULL CHECK (
    execution_mode IN ('single_paper', 'batch', 'stage_only', 'testing', 'backfill', 'replay')
  ),
  status text NOT NULL CHECK (
    status IN ('pending', 'running', 'succeeded', 'failed', 'partially_succeeded', 'cancelled')
  ),
  input_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  created_by text,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  config_hash text,
  schema_version text NOT NULL DEFAULT 'v1',
  trace_ref text,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_events (
  event_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES pipeline_runs(run_id),
  stage_attempt_id text,
  attempt_number integer CHECK (attempt_number IS NULL OR attempt_number > 0),
  idempotency_key text,
  timestamp timestamptz NOT NULL,
  process_name text NOT NULL,
  stage text NOT NULL,
  event_type text NOT NULL CHECK (
    event_type IN (
      'stage_started',
      'stage_succeeded',
      'stage_failed',
      'artifact_created',
      'artifact_validated',
      'artifact_invalid',
      'routing_decision',
      'skipped',
      'warning',
      'retry_scheduled',
      'retry_exhausted'
    )
  ),
  severity text NOT NULL CHECK (
    severity IN ('debug', 'info', 'warning', 'error', 'critical')
  ),
  status text NOT NULL CHECK (
    status IN ('started', 'succeeded', 'failed', 'skipped', 'warning')
  ),
  paper_id text,
  artifact_id text,
  artifact_path text,
  contract_version text,
  schema_version text NOT NULL DEFAULT 'v1',
  trace_ref text,
  message text NOT NULL CHECK (message <> ''),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_id ON pipeline_events(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_stage_attempt_id ON pipeline_events(stage_attempt_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_events_idempotency_key
  ON pipeline_events(idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pipeline_events_paper_id ON pipeline_events(paper_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_process_name ON pipeline_events(process_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_stage ON pipeline_events(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_event_type ON pipeline_events(event_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_timestamp ON pipeline_events(timestamp);

CREATE TABLE IF NOT EXISTS paper_stage_states (
  paper_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked')
  ),
  run_id TEXT,
  artifact_id TEXT,
  artifact_path TEXT,
  error_code TEXT,
  error_message TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (paper_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_paper_stage_states_status ON paper_stage_states(status);
CREATE INDEX IF NOT EXISTS idx_paper_stage_states_run_id ON paper_stage_states(run_id);
CREATE INDEX IF NOT EXISTS idx_paper_stage_states_artifact_id ON paper_stage_states(artifact_id);

CREATE TABLE IF NOT EXISTS artifact_registry (
  artifact_id TEXT PRIMARY KEY,
  paper_id TEXT,
  artifact_kind TEXT NOT NULL,
  stage TEXT NOT NULL,
  artifact_path TEXT NOT NULL,
  content_hash TEXT,
  schema_version TEXT,
  contract_version TEXT,
  producer_run_id TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK (
    validation_status IN ('valid', 'invalid', 'pending', 'unknown')
  ),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifact_registry_paper_id ON artifact_registry(paper_id);
CREATE INDEX IF NOT EXISTS idx_artifact_registry_stage ON artifact_registry(stage);
CREATE INDEX IF NOT EXISTS idx_artifact_registry_kind ON artifact_registry(artifact_kind);
CREATE INDEX IF NOT EXISTS idx_artifact_registry_producer_run_id ON artifact_registry(producer_run_id);
