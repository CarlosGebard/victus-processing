CREATE TABLE IF NOT EXISTS paper_processing_state (
  paper_id TEXT PRIMARY KEY,
  overall_status TEXT NOT NULL,
  current_stage TEXT NOT NULL,
  last_successful_stage TEXT,
  next_stage TEXT,
  active_pipeline_run_id TEXT,
  pipeline_version TEXT NOT NULL,
  config_hash TEXT,
  is_processable BOOLEAN NOT NULL DEFAULT TRUE,
  is_complete BOOLEAN NOT NULL DEFAULT FALSE,
  is_ready_for_export BOOLEAN NOT NULL DEFAULT FALSE,
  is_exported BOOLEAN NOT NULL DEFAULT FALSE,
  blocked_reason TEXT,
  last_error_code TEXT,
  last_error_message TEXT,
  has_pdf BOOLEAN NOT NULL DEFAULT FALSE,
  has_markdown BOOLEAN NOT NULL DEFAULT FALSE,
  has_structured_paper BOOLEAN NOT NULL DEFAULT FALSE,
  has_structured_blocks BOOLEAN NOT NULL DEFAULT FALSE,
  has_evidence_blocks BOOLEAN NOT NULL DEFAULT FALSE,
  has_paper_classification BOOLEAN NOT NULL DEFAULT FALSE,
  has_experiment_map BOOLEAN NOT NULL DEFAULT FALSE,
  has_canonical_evidence BOOLEAN NOT NULL DEFAULT FALSE,
  paper_family TEXT,
  locked_by TEXT,
  locked_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_paper_processing_state_overall_status
  ON paper_processing_state(overall_status);
CREATE INDEX IF NOT EXISTS idx_paper_processing_state_current_stage
  ON paper_processing_state(current_stage);
CREATE INDEX IF NOT EXISTS idx_paper_processing_state_next_stage
  ON paper_processing_state(next_stage);
CREATE INDEX IF NOT EXISTS idx_paper_processing_state_is_complete
  ON paper_processing_state(is_complete);
CREATE INDEX IF NOT EXISTS idx_paper_processing_state_is_ready_for_export
  ON paper_processing_state(is_ready_for_export);
