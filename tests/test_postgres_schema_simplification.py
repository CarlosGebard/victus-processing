from pathlib import Path

from src.application.processing_state import build_processing_state_records
from src.workspace.pipeline_context import PipelineRunContext


ROOT = Path(__file__).resolve().parents[1]


def test_reset_migration_preserves_structured_papers() -> None:
    sql = (ROOT / "ops/sql/005_simplified_postgres_schema.sql").read_text(encoding="utf-8").lower()

    assert "lock table structured_papers" in sql
    assert "drop table if exists structured_papers" not in sql
    assert "truncate structured_papers" not in sql
    assert "create table paper_pipeline_state" in sql
    assert "create table canonical_evidence" in sql


def test_processing_state_surfaces_latest_pipeline_failure(tmp_path: Path) -> None:
    paper_id = "paper_1"
    markdown = tmp_path / "artifacts/markdown" / f"{paper_id}.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_text("# Paper\n", encoding="utf-8")

    records = build_processing_state_records(
        data_dir=tmp_path,
        postgres_facts={
            paper_id: {
                "has_structured_paper": True,
                "has_structured_blocks": True,
                "latest_pipeline_stage": "evidence.map",
                "latest_pipeline_status": "failed",
                "last_error_code": "invalid_mapper_output",
                "last_error_message": "Mapper returned invalid JSON",
            }
        },
    )

    assert records[0]["overall_status"] == "failed"
    assert records[0]["current_stage"] == "evidence.map"
    assert records[0]["next_stage"] == "evidence.map"
    assert records[0]["last_error_code"] == "invalid_mapper_output"


def test_pipeline_context_writes_one_operational_state_per_attempt(tmp_path: Path) -> None:
    class StateStore:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def upsert_paper_pipeline_state(self, record: dict[str, object]) -> None:
            self.records.append(record)

    store = StateStore()
    context = PipelineRunContext.start(
        pipeline_name="victus-processing",
        pipeline_version="v1",
        execution_mode="single_paper",
        process_name="victus.processing.pdf_processing",
        record_store=store,
        lake_dir=tmp_path / "lake",
        runtime_runs_dir=tmp_path / "runtime/runs",
    )
    attempt = context.stage_attempt(stage="pdf.process", paper_id="paper_1")

    event = attempt.event(
        event_type="stage_started",
        severity="info",
        status="started",
        message="Processing started",
        action="start",
    )
    attempt.set_state(status="running", last_event_id=event["event_id"])

    assert len(store.records) == 2
    assert {record["pipeline_state_id"] for record in store.records} == {attempt.stage_attempt_id}
    assert store.records[-1]["paper_id"] == "paper_1"
    assert store.records[-1]["status"] == "running"
