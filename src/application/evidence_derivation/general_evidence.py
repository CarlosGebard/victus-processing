from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from src.application.pdf_processing.llm_markdown import parse_llm_json
from src.application.ports.llm import LLMClient, LLMRequest
from src.application.ports.prompt_registry import PromptSpec


RANK_WEIGHTS = {"A": 1.0, "B": 0.6, "C": 0.25, "D": 0.0, "Reject": 0.0}
DIRECTIONS = ("increase", "decrease", "no_effect", "mixed", "unclear")
RANKS = ("A", "B", "C", "D", "Reject")


def build_general_evidence_artifacts(
    *,
    canonical_evidence: list[dict[str, Any]],
    experiment_map: dict[str, Any],
    build_id: str | None = None,
) -> dict[str, Any]:
    effective_build_id = build_id or stable_build_id(canonical_evidence, [experiment_map])
    exposure_registry = build_exposure_registry(canonical_evidence)
    outcome_registry = build_outcome_registry(canonical_evidence)
    projections = build_evidence_projections(
        canonical_evidence=canonical_evidence,
        experiment_map=experiment_map,
        exposure_registry=exposure_registry,
        outcome_registry=outcome_registry,
        build_id=effective_build_id,
    )
    general_evidence = build_general_evidence(
        projections=[projection for projection in projections if projection["projection_status"] != "rejected"],
        exposure_registry=exposure_registry,
        outcome_registry=outcome_registry,
        build_id=effective_build_id,
    )
    support = build_general_evidence_support(general_evidence)
    return {
        "build_id": effective_build_id,
        "exposure_registry": exposure_registry,
        "outcome_registry": outcome_registry,
        "evidence_projections": projections,
        "general_evidence": general_evidence,
        "general_evidence_support": support,
        "rag_export": build_rag_export(general_evidence=general_evidence, evidence_projections=projections),
    }


def build_corpus_general_evidence_artifacts(
    *,
    papers: list[dict[str, Any]],
    build_id: str | None = None,
) -> dict[str, Any]:
    canonical_evidence = [
        item
        for paper in papers
        for item in paper.get("canonical_evidence") or []
        if isinstance(item, dict)
    ]
    experiment_maps = [paper.get("experiment_map") for paper in papers if isinstance(paper.get("experiment_map"), dict)]
    effective_build_id = build_id or stable_build_id(canonical_evidence, experiment_maps)
    exposure_registry = build_exposure_registry(canonical_evidence)
    outcome_registry = build_outcome_registry(canonical_evidence)
    projections: list[dict[str, Any]] = []
    for paper in papers:
        items = paper.get("canonical_evidence") or []
        experiment_map = paper.get("experiment_map") or {}
        if not isinstance(items, list) or not isinstance(experiment_map, dict):
            raise ValueError("Corpus papers require canonical_evidence list and experiment_map object")
        projections.extend(
            build_evidence_projections(
                canonical_evidence=items,
                experiment_map=experiment_map,
                exposure_registry=exposure_registry,
                outcome_registry=outcome_registry,
                build_id=effective_build_id,
            )
        )
    general_evidence = build_general_evidence(
        projections=[projection for projection in projections if projection["projection_status"] != "rejected"],
        exposure_registry=exposure_registry,
        outcome_registry=outcome_registry,
        build_id=effective_build_id,
    )
    return {
        "build_id": effective_build_id,
        "exposure_registry": exposure_registry,
        "outcome_registry": outcome_registry,
        "evidence_projections": projections,
        "general_evidence": general_evidence,
        "general_evidence_support": build_general_evidence_support(general_evidence),
        "rag_export": build_rag_export(general_evidence=general_evidence, evidence_projections=projections),
    }


def build_exposure_registry(canonical_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = [item.get("raw_exposure") for item in canonical_evidence if item.get("raw_exposure")]
    return [_registry_record(term, prefix="exposure", type_key="exposure_type") for term in _unique_terms(terms)]


def build_outcome_registry(canonical_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms: list[str] = []
    for item in canonical_evidence:
        terms.extend(str(term) for term in item.get("raw_outcomes") or [] if str(term).strip())
    return [_registry_record(term, prefix="outcome", type_key="outcome_type") for term in _unique_terms(terms)]


def build_evidence_projections(
    *,
    canonical_evidence: list[dict[str, Any]],
    experiment_map: dict[str, Any],
    exposure_registry: list[dict[str, Any]],
    outcome_registry: list[dict[str, Any]],
    build_id: str | None = None,
) -> list[dict[str, Any]]:
    exposure_by_name = {record["canonical_name"]: record for record in exposure_registry if record["status"] == "active"}
    outcome_by_name = {record["canonical_name"]: record for record in outcome_registry if record["status"] == "active"}
    scope_by_study = {
        str(scope.get("study_id") or scope.get("experiment_scope_id")): scope
        for scope in experiment_map.get("experiment_scopes") or []
        if isinstance(scope, dict)
    }
    created_at = _now()
    projections: list[dict[str, Any]] = []
    for item in canonical_evidence:
        raw_exposure = item.get("raw_exposure")
        exposure = exposure_by_name.get(_canonical_name(raw_exposure or ""))
        raw_outcomes = item.get("raw_outcomes") or []
        if not raw_outcomes:
            raw_outcomes = [None]
        for raw_outcome in raw_outcomes:
            outcome = outcome_by_name.get(_canonical_name(raw_outcome or ""))
            study_id = str(item.get("study_id") or "unclear")
            scope = scope_by_study.get(study_id, {})
            projection = {
                "projection_id": "",
                "build_id": build_id,
                "canonical_evidence_id": item.get("canonical_evidence_id"),
                "paper_id": item.get("paper_id"),
                "study_id": study_id,
                "exposure_id": exposure["exposure_id"] if exposure else None,
                "outcome_id": outcome["outcome_id"] if outcome else None,
                "organism": item.get("organism") or _organism_from_design(scope.get("study_design")),
                "population_scope": item.get("population"),
                "context_identity": {},
                "context_descriptors": {
                    "subgroup": item.get("subgroup"),
                    "timepoint": item.get("timepoint"),
                    "duration": item.get("duration"),
                    "dose": item.get("dose"),
                    "measurement_method": item.get("measurement_method"),
                },
                "effect_direction": item.get("effect_direction") or "unclear",
                "study_design": scope.get("study_design") or "unclear",
                "study_role_in_paper": scope.get("study_role_in_paper"),
                "evidence_role_in_paper": item.get("evidence_role_in_paper") or "unclear",
                "assertion_type": item.get("assertion_type") or "unclear",
                "evidence_type": item.get("evidence_type"),
                "evidence_rank": "Reject",
                "aggregation_weight": 0.0,
                "rag_use": "reject",
                "causal_language_allowed": False,
                "requires_caveat": True,
                "rank_reason": "",
                "projection_status": "accepted",
                "created_at": created_at,
                "source_quote_count": len(item.get("observations") or []),
                "evidence_text": item.get("evidence_text"),
            }
            rank = rank_projection(projection, canonical=item, exposure=exposure, outcome=outcome)
            projection.update(rank)
            projection["projection_id"] = _stable_id(
                "projection",
                build_id,
                projection["canonical_evidence_id"],
                projection["exposure_id"],
                projection["outcome_id"],
            )
            projections.append(projection)
    return projections


def rank_projection(
    projection: dict[str, Any],
    *,
    canonical: dict[str, Any],
    exposure: dict[str, Any] | None,
    outcome: dict[str, Any] | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    has_grounding = bool(canonical.get("observations") or canonical.get("source_block_ids"))
    if not has_grounding:
        reasons.append("missing source grounding")
    if exposure is None or outcome is None:
        reasons.append("unresolved exposure or outcome")
    if projection["effect_direction"] in {"unclear", "not_applicable"}:
        reasons.append("unclear effect direction")
    if canonical.get("canonical_evidence_status") == "rejected":
        reasons.append("canonical evidence rejected")
    if reasons:
        return _rank_result("Reject", "reject", False, True, "; ".join(reasons), "rejected")

    role = projection["evidence_role_in_paper"]
    assertion = projection["assertion_type"]
    design = projection["study_design"]
    organism = projection["organism"]
    requires_caveat = role == "subgroup_result" or assertion in {"association", "no_association", "mechanistic_link"}
    causal_allowed = assertion in {"causal_effect", "comparative_effect"} and organism == "human"
    if role in {"method_detail", "background_context", "limitation"} or assertion == "methodological":
        return _rank_result("D", "audit_only", False, True, "method/background/limitation evidence", "accepted")
    if organism in {"animal", "in_vitro"} or role in {"mechanistic_result", "descriptive_result"} or assertion == "mechanistic_link":
        return _rank_result("C", "mechanistic_only", False, True, "mechanistic, descriptive, animal, or in vitro evidence", "accepted")
    if role in {"secondary_result", "subgroup_result", "sensitivity_result"}:
        return _rank_result("B", "supporting", False, True, "human secondary/subgroup/sensitivity result", "accepted")
    if (
        organism == "human"
        and role == "primary_result"
        and design in {"rct", "meta_analysis", "systematic_review", "prospective_cohort"}
        and _has_quantitative_or_comparison(canonical)
    ):
        return _rank_result("A", "primary", causal_allowed, requires_caveat, "strong human primary evidence", "accepted")
    if organism == "human":
        return _rank_result("B", "supporting", False, True, "human evidence with caveat", "accepted")
    return _rank_result("C", "supporting", False, True, "indirect or unclear-context evidence", "needs_review")


def build_general_evidence(
    *,
    projections: list[dict[str, Any]],
    exposure_registry: list[dict[str, Any]],
    outcome_registry: list[dict[str, Any]],
    build_id: str | None = None,
) -> list[dict[str, Any]]:
    exposure_names = {record["exposure_id"]: record["display_name"] for record in exposure_registry}
    outcome_names = {record["outcome_id"]: record["display_name"] for record in outcome_registry}
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for projection in projections:
        key = (
            projection.get("exposure_id"),
            projection.get("outcome_id"),
            projection.get("organism"),
            projection.get("population_scope"),
            json.dumps(projection.get("context_identity") or {}, sort_keys=True, separators=(",", ":")),
        )
        groups[key].append(projection)
    created_at = _now()
    output: list[dict[str, Any]] = []
    for key, items in sorted(groups.items(), key=lambda pair: str(pair[0])):
        exposure_id, outcome_id, organism, population_scope, context_identity_json = key
        support_votes = _support_unit_votes(items)
        study_distribution = Counter(vote["direction"] for vote in support_votes)
        evidence_distribution = Counter(item.get("effect_direction") or "unclear" for item in items)
        weighted_support = {direction: 0.0 for direction in DIRECTIONS}
        for vote in support_votes:
            weighted_support[vote["direction"]] += vote["weight"]
        paper_count = len({item.get("paper_id") for item in items if item.get("paper_id")})
        study_count = len(support_votes)
        dominant_direction = _dominant_direction(study_distribution, study_count)
        consensus_level = _consensus_level(study_distribution, paper_count, study_count, items, dominant_direction)
        recommendation_use = _recommendation_use(consensus_level, organism, items)
        requires_caveat = recommendation_use != "directly_usable" or any(item.get("requires_caveat") for item in items)
        causal_allowed = bool(items) and all(item.get("causal_language_allowed") for item in items) and consensus_level in {"moderate", "strong"}
        representative_ids = [item["projection_id"] for item in sorted(items, key=_projection_sort_key)[:5]]
        question = f"What is the evidence linking {exposure_names.get(exposure_id, exposure_id)} to {outcome_names.get(outcome_id, outcome_id)}?"
        conclusion = _template_conclusion(question, dominant_direction, consensus_level, recommendation_use, causal_allowed)
        output.append(
            {
                "general_evidence_id": _stable_id("general_evidence", build_id, *key),
                "build_id": build_id,
                "exposure_id": exposure_id,
                "outcome_id": outcome_id,
                "organism": organism,
                "population_scope": population_scope,
                "context_identity": json.loads(context_identity_json),
                "question": question,
                "dominant_direction": dominant_direction,
                "consensus_level": consensus_level,
                "paper_count": paper_count,
                "study_count": study_count,
                "evidence_count": len(items),
                "study_direction_distribution": _distribution(study_distribution),
                "evidence_direction_distribution": _distribution(evidence_distribution),
                "weighted_support": weighted_support,
                "rank_distribution": {rank: sum(1 for item in items if item.get("evidence_rank") == rank) for rank in RANKS},
                "study_design_distribution": dict(Counter(item.get("study_design") for item in items)),
                "assertion_type_distribution": dict(Counter(item.get("assertion_type") for item in items)),
                "supporting_projection_ids": [item["projection_id"] for item in items if item.get("effect_direction") == dominant_direction],
                "null_projection_ids": [item["projection_id"] for item in items if item.get("effect_direction") == "no_effect"],
                "opposing_projection_ids": _opposing_projection_ids(items, dominant_direction),
                "mixed_projection_ids": [item["projection_id"] for item in items if item.get("effect_direction") == "mixed"],
                "representative_projection_ids": representative_ids,
                "recommendation_use": recommendation_use,
                "causal_language_allowed": causal_allowed,
                "requires_caveat": requires_caveat,
                "caveats": _caveats(consensus_level, recommendation_use, items),
                "conclusion_claim": conclusion,
                "plain_language_conclusion": conclusion,
                "evidence_balance_summary": conclusion,
                "recommendation_interpretation": None if recommendation_use == "not_recommendable" else conclusion,
                "conclusion_generation_method": "deterministic_template",
                "conclusion_prompt_version": None,
                "conclusion_status": "active",
                "status": "needs_review" if recommendation_use == "needs_review" else "active",
                "created_at": created_at,
            }
        )
    return output


def build_general_evidence_support(general_evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    role_fields = {
        "supporting": "supporting_projection_ids",
        "null": "null_projection_ids",
        "opposing": "opposing_projection_ids",
        "mixed": "mixed_projection_ids",
        "representative": "representative_projection_ids",
    }
    return [
        {
            "general_evidence_id": str(item["general_evidence_id"]),
            "projection_id": str(projection_id),
            "support_role": role,
        }
        for item in general_evidence
        for role, field in role_fields.items()
        for projection_id in item.get(field) or []
    ]


def build_rag_export(*, general_evidence: list[dict[str, Any]], evidence_projections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "documents": [
            {"document_type": "general_evidence", "id": item["general_evidence_id"], "payload": item}
            for item in general_evidence
            if item["status"] == "active"
            and item["consensus_level"] != "insufficient"
            and item["recommendation_use"] not in {"not_recommendable", "needs_review"}
        ]
        + [
            {"document_type": "evidence_support", "id": item["projection_id"], "payload": item}
            for item in evidence_projections
            if item["evidence_rank"] in {"A", "B"}
            and item["projection_status"] == "accepted"
            and item["rag_use"] in {"primary", "supporting"}
        ]
    }


def build_conclusion_messages(prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    content = prompt + "\n\n# INPUT\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    return [{"role": "user", "content": content}]


def apply_llm_conclusions(
    *,
    general_evidence: list[dict[str, Any]],
    evidence_projections: list[dict[str, Any]],
    exposure_registry: list[dict[str, Any]],
    outcome_registry: list[dict[str, Any]],
    llm_client: LLMClient,
    model: str,
    prompt: str,
    prompt_spec: PromptSpec | None = None,
    prompt_label: str = "production",
    language: str = "en",
) -> list[dict[str, Any]]:
    exposure_names = {record["exposure_id"]: record["display_name"] for record in exposure_registry}
    outcome_names = {record["outcome_id"]: record["display_name"] for record in outcome_registry}
    projection_by_id = {projection["projection_id"]: projection for projection in evidence_projections}
    output = []
    for item in general_evidence:
        payload = {
            "general_evidence": {
                "general_evidence_id": item["general_evidence_id"],
                "question": item["question"],
                "exposure_display_name": exposure_names.get(item["exposure_id"], item["exposure_id"]),
                "outcome_display_name": outcome_names.get(item["outcome_id"], item["outcome_id"]),
                "organism": item["organism"],
                "population_scope": item["population_scope"],
                "context_identity": item["context_identity"],
                "dominant_direction": item["dominant_direction"],
                "consensus_level": item["consensus_level"],
                "paper_count": item["paper_count"],
                "study_count": item["study_count"],
                "evidence_count": item["evidence_count"],
                "study_direction_distribution": item["study_direction_distribution"],
                "weighted_support": item["weighted_support"],
                "recommendation_use": item["recommendation_use"],
                "causal_language_allowed": item["causal_language_allowed"],
                "requires_caveat": item["requires_caveat"],
                "caveats": item["caveats"],
            },
            "representative_evidence": [
                _representative_evidence_payload(projection_by_id[projection_id])
                for projection_id in item.get("representative_projection_ids") or []
                if projection_id in projection_by_id and projection_by_id[projection_id].get("evidence_rank") in {"A", "B", "C"}
            ],
            "language": language,
        }
        response = llm_client.complete(
            LLMRequest(
                operation="evidence_derivation.general_evidence_conclusion",
                model=model,
                messages=build_conclusion_messages(prompt, payload),
                response_format={"type": "json_object"},
                metadata={
                    "general_evidence_id": item["general_evidence_id"],
                    "prompt_name": prompt_spec.name if prompt_spec else "evidence_derivation/general_evidence",
                    "prompt_version": prompt_spec.version if prompt_spec else None,
                    "prompt_label": prompt_label,
                    "prompt_source": prompt_spec.source if prompt_spec else "local_path",
                },
            )
        )
        conclusion = parse_llm_json(response.text)
        updated = dict(item)
        updated["conclusion_claim"] = str(conclusion.get("conclusion_claim") or updated["conclusion_claim"])
        updated["plain_language_conclusion"] = str(
            conclusion.get("plain_language_conclusion") or updated["plain_language_conclusion"]
        )
        updated["evidence_balance_summary"] = str(
            conclusion.get("evidence_balance_summary") or updated["evidence_balance_summary"]
        )
        recommendation = conclusion.get("recommendation_interpretation")
        updated["recommendation_interpretation"] = str(recommendation) if recommendation is not None else None
        if isinstance(conclusion.get("conclusion_caveats"), list):
            updated["caveats"] = [str(caveat) for caveat in conclusion["conclusion_caveats"]]
        status = conclusion.get("conclusion_status")
        updated["conclusion_status"] = status if status in {"active", "needs_review", "rejected"} else "needs_review"
        updated["conclusion_generation_method"] = "llm"
        updated["conclusion_prompt_version"] = prompt_spec.version if prompt_spec else None
        if validate_conclusion_text(updated):
            updated["conclusion_status"] = "needs_review"
        output.append(updated)
    return output


def validate_conclusion_text(general_evidence: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(general_evidence.get(key) or "")
        for key in ("conclusion_claim", "plain_language_conclusion", "evidence_balance_summary", "recommendation_interpretation")
    ).lower()
    errors: list[str] = []
    if not general_evidence.get("causal_language_allowed") and re.search(r"\b(causes|prevents|cures|reduces)\b", text):
        errors.append("causal wording is not allowed")
    if general_evidence.get("recommendation_use") == "mechanistic_only" and not re.search(
        r"\b(mechanistic|preclinical|animal|in vitro)\b", text
    ):
        errors.append("mechanistic-only conclusion must state evidence type")
    if general_evidence.get("consensus_level") == "insufficient" and re.search(r"\b(clear|strong|supports|shows)\b", text):
        errors.append("insufficient evidence conclusion sounds definitive")
    if general_evidence.get("dominant_direction") == "no_effect" and re.search(r"\b(improvement|worsening|improves|worsens)\b", text):
        errors.append("no-effect conclusion claims change")
    if general_evidence.get("consensus_level") == "mixed" and not re.search(r"\b(conflicting|inconsistent|mixed)\b", text):
        errors.append("mixed evidence conclusion must mention conflict")
    return errors


def _representative_evidence_payload(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "projection_id": projection["projection_id"],
        "evidence_text": projection.get("evidence_text") or "",
        "evidence_rank": projection["evidence_rank"],
        "study_design": projection["study_design"],
        "effect_direction": projection["effect_direction"],
        "assertion_type": projection["assertion_type"],
    }


def _registry_record(term: str, *, prefix: str, type_key: str) -> dict[str, Any]:
    canonical_name = _canonical_name(term)
    review = not canonical_name
    record_type = _classify_exposure(term) if prefix == "exposure" else _classify_outcome(term)
    return {
        f"{prefix}_id": f"{prefix}.{canonical_name or 'unresolved'}",
        "canonical_name": canonical_name or "unresolved",
        "display_name": _display_name(canonical_name or term),
        type_key: record_type,
        "aliases": sorted({str(term).strip()}),
        f"parent_{prefix}_id": None,
        "definition": None,
        "status": "needs_review" if review else "active",
        "created_by": "deterministic",
        "confidence": "low" if review else "medium",
    }


def _unique_terms(terms: list[Any]) -> list[str]:
    by_name: dict[str, str] = {}
    for term in terms:
        raw = str(term or "").strip()
        name = _canonical_name(raw)
        if not name:
            continue
        by_name.setdefault(name, raw)
    return [by_name[name] for name in sorted(by_name)]


def _canonical_name(term: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    for suffix in ("_consumption", "_intake"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    value = value.replace("whole_egg", "egg")
    return value


def _display_name(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _classify_exposure(term: str) -> str:
    value = term.lower()
    if any(token in value for token in ("diet", "egg", "fiber", "starch", "food")):
        return "food"
    if any(token in value for token in ("exercise", "training")):
        return "exercise"
    if "sleep" in value:
        return "sleep"
    return "other"


def _classify_outcome(term: str) -> str:
    value = term.lower()
    if any(token in value for token in ("cholesterol", "glucose", "insulin", "biomarker")):
        return "biomarker"
    if any(token in value for token in ("weight", "bmi", "waist")):
        return "anthropometric"
    if any(token in value for token in ("microbiome", "taxa", "bacteria")):
        return "microbiome"
    return "other"


def _rank_result(
    rank: str,
    rag_use: str,
    causal_language_allowed: bool,
    requires_caveat: bool,
    reason: str,
    status: str,
) -> dict[str, Any]:
    return {
        "evidence_rank": rank,
        "aggregation_weight": RANK_WEIGHTS[rank],
        "rag_use": rag_use,
        "causal_language_allowed": causal_language_allowed,
        "requires_caveat": requires_caveat,
        "rank_reason": reason,
        "projection_status": status,
    }


def _has_quantitative_or_comparison(canonical: dict[str, Any]) -> bool:
    quantitative = canonical.get("quantitative_data") or {}
    return bool(canonical.get("comparator") or quantitative.get("summary") or quantitative.get("values"))


def _support_unit_votes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        key = (
            item.get("paper_id"),
            item.get("study_id"),
            item.get("exposure_id"),
            item.get("outcome_id"),
            item.get("organism"),
            item.get("population_scope"),
            json.dumps(item.get("context_identity") or {}, sort_keys=True, separators=(",", ":")),
        )
        units[key].append(item)
    votes = []
    for unit_items in units.values():
        strong = [item for item in unit_items if item.get("evidence_rank") in {"A", "B"}] or unit_items
        directions = {item.get("effect_direction") or "unclear" for item in strong}
        direction = next(iter(directions)) if len(directions) == 1 else "mixed"
        votes.append({"direction": direction, "weight": min(1.0, max(float(item.get("aggregation_weight") or 0.0) for item in strong))})
    return votes


def _dominant_direction(distribution: Counter[str], study_count: int) -> str:
    if study_count < 1:
        return "unclear"
    direction, count = distribution.most_common(1)[0]
    if count / study_count < 0.55:
        return "mixed"
    return direction


def _consensus_level(
    distribution: Counter[str],
    paper_count: int,
    study_count: int,
    items: list[dict[str, Any]],
    dominant_direction: str,
) -> str:
    if paper_count < 2 or study_count < 2 or dominant_direction == "unclear":
        return "insufficient"
    dominant_ratio = distribution[dominant_direction] / study_count
    opposing_ratio = sum(count for direction, count in distribution.items() if direction not in {dominant_direction, "unclear"}) / study_count
    ab_count = sum(1 for item in items if item.get("evidence_rank") in {"A", "B"})
    if opposing_ratio > 0.30 or dominant_ratio < 0.55:
        return "mixed"
    if paper_count >= 8 and study_count >= 10 and dominant_ratio >= 0.70 and opposing_ratio <= 0.15 and ab_count >= len(items) / 2:
        return "strong"
    if paper_count >= 4 and study_count >= 5 and dominant_ratio >= 0.55 and opposing_ratio <= 0.30:
        return "moderate"
    return "weak"


def _recommendation_use(consensus_level: str, organism: str, items: list[dict[str, Any]]) -> str:
    if any(item.get("projection_status") == "needs_review" for item in items):
        return "needs_review"
    if organism in {"animal", "in_vitro"} or all(item.get("rag_use") == "mechanistic_only" for item in items):
        return "mechanistic_only"
    if consensus_level in {"insufficient", "mixed"}:
        return "not_recommendable"
    if consensus_level in {"moderate", "strong"} and any(item.get("evidence_rank") == "A" for item in items):
        return "directly_usable"
    return "usable_with_caveat"


def _distribution(counter: Counter[str]) -> dict[str, int]:
    return {direction: int(counter.get(direction, 0)) for direction in DIRECTIONS}


def _opposing_projection_ids(items: list[dict[str, Any]], dominant_direction: str) -> list[str]:
    if dominant_direction in {"mixed", "unclear"}:
        return []
    return [
        item["projection_id"]
        for item in items
        if item.get("effect_direction") not in {dominant_direction, "unclear", "mixed"}
    ]


def _projection_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    rank_order = {"A": 0, "B": 1, "C": 2, "D": 3, "Reject": 4}
    return (rank_order.get(item.get("evidence_rank"), 9), str(item.get("projection_id")))


def _caveats(consensus_level: str, recommendation_use: str, items: list[dict[str, Any]]) -> list[str]:
    caveats = []
    if consensus_level in {"weak", "insufficient"}:
        caveats.append("Evidence is limited.")
    if consensus_level == "mixed":
        caveats.append("Evidence is conflicting.")
    if recommendation_use == "mechanistic_only":
        caveats.append("Evidence is mechanistic or preclinical and not direct human recommendation evidence.")
    if any(item.get("assertion_type") in {"association", "no_association"} for item in items):
        caveats.append("Association evidence should not be interpreted as causal.")
    return caveats


def _template_conclusion(
    question: str,
    dominant_direction: str,
    consensus_level: str,
    recommendation_use: str,
    causal_allowed: bool,
) -> str:
    if consensus_level == "insufficient":
        return f"{question} The available evidence is insufficient for a firm conclusion."
    if consensus_level == "mixed":
        return f"{question} The evidence is mixed, with conflicting findings across studies."
    verb = "shows" if causal_allowed else "is associated with"
    if recommendation_use == "mechanistic_only":
        return f"{question} The evidence is mechanistic or preclinical and suggests {dominant_direction}, not direct human recommendation evidence."
    return f"{question} The current evidence {verb} {dominant_direction} with {consensus_level} consensus."


def _organism_from_design(study_design: Any) -> str:
    if study_design == "animal_experiment":
        return "animal"
    if study_design == "in_vitro":
        return "in_vitro"
    return "unclear"


def _stable_id(prefix: str, *parts: Any) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def stable_build_id(
    canonical_evidence: list[dict[str, Any]],
    experiment_maps: list[dict[str, Any]] | None = None,
) -> str:
    evidence_payload = sorted(canonical_evidence, key=lambda item: str(item.get("canonical_evidence_id") or ""))
    map_payload = sorted(
        experiment_maps or [],
        key=lambda item: str(item.get("paper_id") or item.get("experiment_map_id") or ""),
    )
    return _stable_id("evidence_build", evidence_payload, map_payload)


def _now() -> str:
    return datetime.now(UTC).isoformat()
