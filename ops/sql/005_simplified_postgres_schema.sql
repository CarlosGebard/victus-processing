BEGIN;

-- This is an intentional reset migration. structured_papers is the only table
-- whose rows are preserved; all other pipeline tables are rebuilt from zero.
CREATE TABLE IF NOT EXISTS structured_papers (
  paper_id TEXT PRIMARY KEY,
  payload JSONB NOT NULL,
  producer_run_id TEXT,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_structured_papers_producer_run_id
  ON structured_papers(producer_run_id);

LOCK TABLE structured_papers IN SHARE ROW EXCLUSIVE MODE;

DROP TABLE IF EXISTS pipeline_events;
DROP TABLE IF EXISTS paper_stage_states;
DROP TABLE IF EXISTS artifact_registry;
DROP TABLE IF EXISTS pipeline_runs;
DROP TABLE IF EXISTS evidence_blocks;
DROP TABLE IF EXISTS paper_pipeline_state;
DROP TABLE IF EXISTS paper_processing_state;
DROP TABLE IF EXISTS canonical_evidence;
DROP TABLE IF EXISTS experiment_maps;
DROP TABLE IF EXISTS paper_classifications;
DROP TABLE IF EXISTS structured_blocks;

CREATE TABLE paper_pipeline_state (
  pipeline_state_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'warning')
  ),
  attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
  run_id TEXT NOT NULL,
  pipeline_name TEXT NOT NULL,
  pipeline_version TEXT NOT NULL,
  execution_mode TEXT NOT NULL,
  input_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  artifact_path TEXT,
  error_code TEXT,
  error_message TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (paper_id, run_id, stage, attempt_number)
);

CREATE INDEX idx_paper_pipeline_state_paper_id
  ON paper_pipeline_state(paper_id);
CREATE INDEX idx_paper_pipeline_state_run_id
  ON paper_pipeline_state(run_id);
CREATE INDEX idx_paper_pipeline_state_status
  ON paper_pipeline_state(status);
CREATE INDEX idx_paper_pipeline_state_updated_at
  ON paper_pipeline_state(updated_at DESC);

CREATE TABLE paper_processing_state (
  paper_id TEXT PRIMARY KEY,
  overall_status TEXT NOT NULL,
  current_stage TEXT NOT NULL,
  last_successful_stage TEXT,
  next_stage TEXT,
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
  has_paper_classification BOOLEAN NOT NULL DEFAULT FALSE,
  has_experiment_map BOOLEAN NOT NULL DEFAULT FALSE,
  has_canonical_evidence BOOLEAN NOT NULL DEFAULT FALSE,
  paper_family TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_paper_processing_state_overall_status
  ON paper_processing_state(overall_status);
CREATE INDEX idx_paper_processing_state_current_stage
  ON paper_processing_state(current_stage);
CREATE INDEX idx_paper_processing_state_next_stage
  ON paper_processing_state(next_stage);
CREATE INDEX idx_paper_processing_state_is_complete
  ON paper_processing_state(is_complete);
CREATE INDEX idx_paper_processing_state_is_ready_for_export
  ON paper_processing_state(is_ready_for_export);

CREATE TABLE structured_blocks (
  block_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  content_hash TEXT,
  block_order INTEGER NOT NULL,
  section_path JSONB NOT NULL DEFAULT '[]'::jsonb,
  section_type TEXT NOT NULL,
  content_kind TEXT NOT NULL,
  text TEXT NOT NULL,
  payload JSONB NOT NULL,
  producer_run_id TEXT,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_structured_blocks_paper_id ON structured_blocks(paper_id);
CREATE INDEX idx_structured_blocks_section_type ON structured_blocks(section_type);
CREATE INDEX idx_structured_blocks_content_kind ON structured_blocks(content_kind);
CREATE INDEX idx_structured_blocks_producer_run_id ON structured_blocks(producer_run_id);

CREATE TABLE paper_classifications (
  paper_id TEXT NOT NULL,
  producer_run_id TEXT NOT NULL DEFAULT 'unknown',
  paper_family TEXT NOT NULL,
  paper_type TEXT NOT NULL,
  evidence_generation_mode TEXT NOT NULL,
  has_original_experiments BOOLEAN NOT NULL,
  has_systematic_search BOOLEAN NOT NULL,
  has_meta_analysis BOOLEAN NOT NULL,
  classification_confidence DOUBLE PRECISION NOT NULL,
  payload JSONB NOT NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (paper_id, producer_run_id)
);

CREATE INDEX idx_paper_classifications_family ON paper_classifications(paper_family);
CREATE INDEX idx_paper_classifications_mode ON paper_classifications(evidence_generation_mode);

CREATE TABLE experiment_maps (
  experiment_map_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  producer_run_id TEXT,
  experiment_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
  unmapped_block_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  payload JSONB NOT NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_experiment_maps_paper_id ON experiment_maps(paper_id);
CREATE INDEX idx_experiment_maps_producer_run_id ON experiment_maps(producer_run_id);

CREATE TABLE canonical_evidence (
  canonical_evidence_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  producer_run_id TEXT,
  experiment_map_id TEXT,
  experiment_scope_id TEXT,
  study_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  evidence_role_in_paper TEXT NOT NULL,
  assertion_type TEXT NOT NULL,
  organism TEXT,
  effect_direction TEXT NOT NULL,
  evidence_text TEXT NOT NULL,
  source_block_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  observations JSONB NOT NULL DEFAULT '[]'::jsonb,
  quantitative_data JSONB,
  payload JSONB NOT NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_canonical_evidence_paper_id ON canonical_evidence(paper_id);
CREATE INDEX idx_canonical_evidence_type ON canonical_evidence(evidence_type);
CREATE INDEX idx_canonical_evidence_effect_direction ON canonical_evidence(effect_direction);
CREATE INDEX idx_canonical_evidence_study_id ON canonical_evidence(study_id);
CREATE INDEX idx_canonical_evidence_experiment_map_id ON canonical_evidence(experiment_map_id);
CREATE INDEX idx_canonical_evidence_producer_run_id ON canonical_evidence(producer_run_id);

COMMIT;
