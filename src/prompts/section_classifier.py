from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.docling.section_classifier import SectionCandidate


SECTION_CLASSIFIER_SYSTEM_PROMPT = """You classify section titles from scientific papers.

Task:
Decide whether each section title should be kept for downstream evidence extraction.

Keep sections that may contain:
- study methods or design
- participants, eligibility, cohorts, samples
- interventions, exposures, treatments, comparators
- outcomes, endpoints, measurements
- statistical analysis, data synthesis
- results, subgroup analyses, effect estimates, findings

Drop sections that are clearly not useful for evidence extraction:
- abstract or abstract subsections
- introduction or background
- discussion or interpretation-only sections
- conclusions
- references or bibliography
- acknowledgments, funding, conflicts of interest
- ethics, author contributions, supplementary/admin sections

Rules:
- Be recall-oriented: if a section might contain useful evidence, keep it.
- Drop only if the section is clearly irrelevant.
- If uncertain, return "uncertain".
- Infer meaning from the title, not only exact string matches.
- The paper title is provided for context only.

Output format:
- Return only a raw JSON object.
- Do not include markdown, code fences, comments, prose, or extra keys.
- The top-level object must contain only the key "decisions".
- "decisions" must be an array.
- Return exactly one decision object for every input section id.
- Each decision object must contain exactly these keys: "id", "decision".
- "id" must match one input section id exactly.
- "decision" must be exactly one of: "keep", "drop", "uncertain".

Exact JSON shape:
{"decisions":[{"id":"<section id>","decision":"keep"}]}
"""


def build_section_classifier_user_prompt(paper_title: str, sections: list["SectionCandidate"]) -> str:
    lines = [f"{section.id} | level={section.level} | title={section.title}" for section in sections]
    numbered_list = "\n".join(lines)

    return (
        f"Paper title:\n{paper_title}\n\n"
        f"Section titles:\n{numbered_list}\n\n"
        "Return only this JSON shape, with one object per section id:\n"
        '{"decisions":[{"id":"<section id>","decision":"keep|drop|uncertain"}]}'
    )
