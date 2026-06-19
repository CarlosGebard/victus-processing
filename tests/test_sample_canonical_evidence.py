from __future__ import annotations

from pathlib import Path

from ops.scripts.sample_canonical_evidence import write_sample_bundle


def test_canonical_evidence_sample_writes_bundle_in_one_folder(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "source-pdfs"
    sample_dir = tmp_path / "judge-sample"
    paper_id = "paper_a"
    pdf_dir.mkdir()
    (pdf_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n")

    written = write_sample_bundle(
        sample_dir=sample_dir,
        pdf_dir=pdf_dir,
        paper_ids=[paper_id, "paper_missing_pdf"],
        evidence_rows=[
            {
                "canonical_evidence_id": "ev_1",
                "paper_id": paper_id,
                "evidence_type": "association",
                "direction": "positive",
                "evidence_text": "Diet quality improved a biomarker.",
                "source_block_ids": ["b1"],
                "payload": {"canonical_evidence_id": "ev_1"},
            }
        ],
        seed="test-seed",
    )

    assert written["sample_dir"] == sample_dir.resolve()
    assert (sample_dir / "canonical_evidence.csv").exists()
    assert (sample_dir / "canonical_evidence.json").exists()
    assert (sample_dir / "manifest.csv").exists()
    assert (sample_dir / "sample_metadata.json").exists()
    assert (sample_dir / "pdfs" / f"{paper_id}.pdf").read_bytes() == b"%PDF-1.4\n"
    assert not (sample_dir / "pdfs" / "paper_missing_pdf.pdf").exists()
    manifest = (sample_dir / "manifest.csv").read_text(encoding="utf-8")
    assert "paper_missing_pdf" in manifest
    assert "True" in manifest
