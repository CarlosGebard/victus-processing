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

CREATE INDEX IF NOT EXISTS idx_evidence_blocks_paper_id
  ON evidence_blocks(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_section_type
  ON evidence_blocks(section_type);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_content_kind
  ON evidence_blocks(content_kind);
CREATE INDEX IF NOT EXISTS idx_evidence_blocks_producer_run_id
  ON evidence_blocks(producer_run_id);

ALTER TABLE paper_processing_state
  ADD COLUMN IF NOT EXISTS has_pdf BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_markdown BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_structured_paper BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_structured_blocks BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_evidence_blocks BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_paper_classification BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_experiment_map BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_canonical_evidence BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS paper_family TEXT;
