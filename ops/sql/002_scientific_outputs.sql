CREATE TABLE IF NOT EXISTS structured_papers (
  paper_id TEXT PRIMARY KEY,
  payload JSONB NOT NULL,
  producer_run_id TEXT,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_structured_papers_producer_run_id ON structured_papers(producer_run_id);

CREATE TABLE IF NOT EXISTS structured_blocks (
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

CREATE INDEX IF NOT EXISTS idx_structured_blocks_paper_id ON structured_blocks(paper_id);
CREATE INDEX IF NOT EXISTS idx_structured_blocks_section_type ON structured_blocks(section_type);
CREATE INDEX IF NOT EXISTS idx_structured_blocks_content_kind ON structured_blocks(content_kind);
CREATE INDEX IF NOT EXISTS idx_structured_blocks_producer_run_id ON structured_blocks(producer_run_id);

CREATE TABLE IF NOT EXISTS evidence_blocks (
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

CREATE INDEX IF NOT EXISTS idx_evidence_blocks_paper_id ON evidence_blocks(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_section_type ON evidence_blocks(section_type);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_content_kind ON evidence_blocks(content_kind);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_producer_run_id ON evidence_blocks(producer_run_id);

CREATE TABLE IF NOT EXISTS paper_classifications (
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

CREATE INDEX IF NOT EXISTS idx_paper_classifications_family ON paper_classifications(paper_family);
CREATE INDEX IF NOT EXISTS idx_paper_classifications_mode ON paper_classifications(evidence_generation_mode);

CREATE TABLE IF NOT EXISTS experiment_maps (
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

CREATE INDEX IF NOT EXISTS idx_experiment_maps_paper_id ON experiment_maps(paper_id);
CREATE INDEX IF NOT EXISTS idx_experiment_maps_producer_run_id ON experiment_maps(producer_run_id);

CREATE TABLE IF NOT EXISTS canonical_evidence (
  canonical_evidence_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  producer_run_id TEXT,
  experiment_map_id TEXT,
  experiment_scope_id TEXT,
  evidence_type TEXT NOT NULL,
  organism TEXT,
  direction TEXT NOT NULL,
  evidence_text TEXT NOT NULL,
  source_block_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  observations JSONB NOT NULL DEFAULT '[]'::jsonb,
  quantitative_data JSONB,
  payload JSONB NOT NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_canonical_evidence_paper_id ON canonical_evidence(paper_id);
CREATE INDEX IF NOT EXISTS idx_canonical_evidence_type ON canonical_evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_canonical_evidence_direction ON canonical_evidence(direction);
CREATE INDEX IF NOT EXISTS idx_canonical_evidence_experiment_map_id ON canonical_evidence(experiment_map_id);
CREATE INDEX IF NOT EXISTS idx_canonical_evidence_producer_run_id ON canonical_evidence(producer_run_id);
