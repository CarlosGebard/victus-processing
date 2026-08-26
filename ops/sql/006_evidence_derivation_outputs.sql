BEGIN;

CREATE TABLE IF NOT EXISTS exposure_registry (
  exposure_id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  exposure_type TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  parent_exposure_id TEXT,
  definition TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  confidence TEXT NOT NULL,
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outcome_registry (
  outcome_id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  outcome_type TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  parent_outcome_id TEXT,
  definition TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  confidence TEXT NOT NULL,
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence_projections (
  projection_id TEXT PRIMARY KEY,
  build_id TEXT NOT NULL,
  canonical_evidence_id TEXT NOT NULL,
  paper_id TEXT NOT NULL,
  study_id TEXT NOT NULL,
  exposure_id TEXT,
  outcome_id TEXT,
  organism TEXT,
  population_scope TEXT,
  context_identity JSONB NOT NULL DEFAULT '{}'::jsonb,
  effect_direction TEXT NOT NULL,
  study_design TEXT NOT NULL,
  evidence_rank TEXT NOT NULL,
  aggregation_weight DOUBLE PRECISION NOT NULL,
  rag_use TEXT NOT NULL,
  causal_language_allowed BOOLEAN NOT NULL,
  requires_caveat BOOLEAN NOT NULL,
  rank_reason TEXT NOT NULL,
  projection_status TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_projections_build_id ON evidence_projections(build_id);
CREATE INDEX IF NOT EXISTS idx_evidence_projections_canonical_id ON evidence_projections(canonical_evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_projections_paper_id ON evidence_projections(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_projections_pair ON evidence_projections(exposure_id, outcome_id);
CREATE INDEX IF NOT EXISTS idx_evidence_projections_rank ON evidence_projections(evidence_rank);

CREATE TABLE IF NOT EXISTS general_evidence (
  general_evidence_id TEXT PRIMARY KEY,
  build_id TEXT NOT NULL,
  exposure_id TEXT,
  outcome_id TEXT,
  organism TEXT,
  population_scope TEXT,
  context_identity JSONB NOT NULL DEFAULT '{}'::jsonb,
  question TEXT NOT NULL,
  dominant_direction TEXT NOT NULL,
  consensus_level TEXT NOT NULL,
  paper_count INTEGER NOT NULL CHECK (paper_count >= 0),
  study_count INTEGER NOT NULL CHECK (study_count >= 0),
  evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
  recommendation_use TEXT NOT NULL,
  causal_language_allowed BOOLEAN NOT NULL,
  requires_caveat BOOLEAN NOT NULL,
  conclusion_claim TEXT NOT NULL,
  conclusion_status TEXT NOT NULL,
  status TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_general_evidence_build_id ON general_evidence(build_id);
CREATE INDEX IF NOT EXISTS idx_general_evidence_pair ON general_evidence(exposure_id, outcome_id);
CREATE INDEX IF NOT EXISTS idx_general_evidence_status ON general_evidence(status);
CREATE INDEX IF NOT EXISTS idx_general_evidence_consensus ON general_evidence(consensus_level);

CREATE TABLE IF NOT EXISTS general_evidence_support (
  general_evidence_id TEXT NOT NULL REFERENCES general_evidence(general_evidence_id) ON DELETE CASCADE,
  projection_id TEXT NOT NULL REFERENCES evidence_projections(projection_id) ON DELETE CASCADE,
  support_role TEXT NOT NULL CHECK (
    support_role IN ('supporting', 'null', 'opposing', 'mixed', 'representative')
  ),
  PRIMARY KEY (general_evidence_id, projection_id, support_role)
);

CREATE INDEX IF NOT EXISTS idx_general_evidence_support_projection
  ON general_evidence_support(projection_id);

COMMIT;
