# PostgreSQL Schema

Migrations 005 and 006 are the active schema sources.

```mermaid
erDiagram
  paper_pipeline_state {
    text pipeline_state_id PK
    text paper_id
    text stage
    text status
    integer attempt_number
    text run_id
    text pipeline_name
    text pipeline_version
    text execution_mode
    jsonb input_scope
    text artifact_path
    text error_code
    text error_message
    jsonb metadata
    timestamptz started_at
    timestamptz ended_at
    timestamptz updated_at
  }

  paper_processing_state {
    text paper_id PK
    text overall_status
    text current_stage
    text last_successful_stage
    text next_stage
    boolean is_processable
    boolean is_complete
    boolean is_ready_for_export
    boolean is_exported
    text blocked_reason
    text last_error_code
    text last_error_message
    boolean has_pdf
    boolean has_markdown
    boolean has_structured_paper
    boolean has_structured_blocks
    boolean has_paper_classification
    boolean has_experiment_map
    boolean has_canonical_evidence
    text paper_family
    timestamptz updated_at
  }

  structured_papers {
    text paper_id PK
    jsonb payload
    text producer_run_id
    text schema_version
    timestamptz created_at
    timestamptz updated_at
  }

  structured_blocks {
    text block_id PK
    text paper_id
    text content_hash
    integer block_order
    jsonb section_path
    text section_type
    text content_kind
    text text
    jsonb payload
    text producer_run_id
    text schema_version
    timestamptz created_at
    timestamptz updated_at
  }

  paper_classifications {
    text paper_id PK
    text producer_run_id PK
    text paper_family
    text paper_type
    text evidence_generation_mode
    boolean has_original_experiments
    boolean has_systematic_search
    boolean has_meta_analysis
    double classification_confidence
    jsonb payload
    text schema_version
    timestamptz created_at
    timestamptz updated_at
  }

  experiment_maps {
    text experiment_map_id PK
    text paper_id
    text producer_run_id
    jsonb experiment_scopes
    jsonb unmapped_block_ids
    jsonb payload
    text schema_version
    timestamptz created_at
    timestamptz updated_at
  }

  canonical_evidence {
    text canonical_evidence_id PK
    text paper_id
    text producer_run_id
    text experiment_map_id
    text experiment_scope_id
    text study_id
    text evidence_type
    text evidence_role_in_paper
    text assertion_type
    text organism
    text effect_direction
    text evidence_text
    jsonb source_block_ids
    jsonb observations
    jsonb quantitative_data
    jsonb payload
    text schema_version
    timestamptz created_at
    timestamptz updated_at
  }

  exposure_registry {
    text exposure_id PK
    text canonical_name
    text display_name
    text exposure_type
    jsonb payload
  }

  outcome_registry {
    text outcome_id PK
    text canonical_name
    text display_name
    text outcome_type
    jsonb payload
  }

  evidence_projections {
    text projection_id PK
    text build_id
    text canonical_evidence_id
    text paper_id
    text exposure_id
    text outcome_id
    text evidence_rank
    text projection_status
    jsonb payload
  }

  general_evidence {
    text general_evidence_id PK
    text build_id
    text exposure_id
    text outcome_id
    text consensus_level
    integer paper_count
    integer study_count
    integer evidence_count
    text status
    jsonb payload
  }

  general_evidence_support {
    text general_evidence_id PK,FK
    text projection_id PK,FK
    text support_role PK
  }

  paper_pipeline_state }o--|| paper_processing_state : summarizes_into
  structured_papers ||--o{ structured_blocks : contains
  structured_papers ||--o{ paper_classifications : classified_as
  structured_papers ||--o{ experiment_maps : mapped_by
  structured_papers ||--o{ canonical_evidence : yields
  experiment_maps ||--o{ canonical_evidence : scopes
  structured_blocks ||--o{ canonical_evidence : grounds
  canonical_evidence ||--o{ evidence_projections : classifies_into
  exposure_registry ||--o{ evidence_projections : normalizes
  outcome_registry ||--o{ evidence_projections : normalizes
  exposure_registry ||--o{ general_evidence : groups
  outcome_registry ||--o{ general_evidence : groups
  general_evidence ||--o{ general_evidence_support : contains
  evidence_projections ||--o{ general_evidence_support : supports
```

PostgreSQL stores durable scientific outputs, build-versioned evidence
classification and aggregation, per-attempt pipeline state, and a derived
per-paper dashboard state. RAG export remains a local JSON handoff.
