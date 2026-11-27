"""Sanitized export of study results for the manuscript artifact.

Only counts, public clause identifiers, control kinds and aggregate outcomes leave
the study directory. Private case names, prompts, trajectories, submissions and
logs stay where they are.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import admission, aggregate
from .attempts import schedule
from .clausemap import ClauseMap
from .e1config import StudyConfig
from .exclusions import Exclusions
from .inventory import task_for
from .paths import StudyPaths


def _e0(paths: StudyPaths) -> dict[str, Any]:
    summary = admission.report(paths)
    tasks = []
    for item in summary["tasks"]:
        controls: Counter[str] = Counter()
        for row in item.get("controls", []):
            if row.get("informational"):
                controls["strictReadingRejected" if row.get("problems") else "strictReadingAccepted"] += 1
            elif row.get("admissible"):
                controls[str(row["kind"])] += 1
            else:
                controls["inadmissible"] += 1
        tasks.append(
            {
                "task": item["task"],
                "kind": item["kind"],
                "sourceFamily": item["sourceFamily"],
                "taskVersion": item.get("taskVersion"),
                "admitted": item["admitted"],
                "compatibilityQualified": item["compatibilityQualified"],
                "notQualifiedBecause": item.get("notQualifiedBecause"),
                "cases": item.get("cases", {}),
                "overlapCases": item.get("overlapCases", 0),
                "overConstrainedCases": len(item.get("overConstrainedCases", [])),
                "clauses": item.get("clauses", {}),
                "excludedClauses": item.get("excludedClauses", []),
                "admissibleControls": dict(controls),
            }
        )
    return {
        "registered": summary["registered"],
        "admitted": summary["admitted"],
        "compatibilityQualified": summary["compatibilityQualified"],
        "excluded": summary["excluded"],
        "tasks": tasks,
    }


def _role_counts(
    paths: StudyPaths, record: dict[str, Any], cache: dict[str, ClauseMap]
) -> dict[str, dict[str, int]]:
    """Observation counts of the audited requested-change and preserved-contract cases (counts only)."""
    key = str(record["task"])
    if key not in cache:
        task = task_for(key)
        cache[key] = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
    observed = record.get("cases") or {}
    counts = {}
    for role in ("target", "preserved"):
        seen = Counter(observed.get(case, "U") for case in cache[key].case_ids(role, audited=True))
        counts[role] = {"total": sum(seen.values()), "P": seen["P"], "F": seen["F"], "U": seen["U"]}
    return counts


def _e1(
    paths: StudyPaths,
    config: StudyConfig,
    digest: str,
    exclusions: Exclusions,
    excluded_attempts: set[str],
    models: tuple[str, ...] = (),
) -> dict[str, Any]:
    root = paths.data_root / "e1" / config.study_id
    reported = [model for model in config.models if not models or model.id in models]
    kept = {model.id for model in reported}
    # Excluded tasks leave before anything reads their clause maps; their records stay on disk.
    ledger = aggregate.load_ledger(root, excluded=exclusions.tasks)
    records = [item for item in ledger if item["model"] in kept]
    dropped = sum(
        item["model"] in kept and item["task"] in exclusions.tasks
        for item in aggregate.load_ledger(root, excluded=(), adjudicated=False)
    )
    summary = aggregate.summarize(records, config.repeats)
    maps: dict[str, ClauseMap] = {}
    attempts = [
        {
            "attempt": item["attempt_id"],
            "model": item["model"],
            "task": item["task"],
            "repeat": item["repeat"],
            "kind": item["kind"],
            "outcome": item["outcome"],
            "auditedOutcome": item.get("auditedOutcome"),
            "score": item.get("score"),
            "complete": item.get("complete"),
            "targetOutcome": item["targetOutcome"],
            "preservedOutcome": item["preservedOutcome"],
            "observations": dict(Counter((item.get("cases") or {}).values())),
            "roleObservations": _role_counts(paths, item, maps),
            "nativeOutcome": item.get("nativeOutcome"),
            "adjudication": item.get("adjudication"),
            "rescored": "rescoredAt" in item,
            "voidedGenerationStarts": len(item.get("voidedGenerationStarts") or []),
            "generation": {
                key: (item.get("generation") or {}).get(key)
                for key in ("steps", "exitStatus", "durationSeconds", "containerFailure", "terminationReason")
            },
            "usage": {
                key: (item.get("usage") or {}).get(key)
                for key in (
                    "calls",
                    "prompt_tokens",
                    "completion_tokens",
                    "reasoning_tokens",
                    "cached_prompt_tokens",
                )
            },
            "evaluatorExecutions": len(item.get("executions") or []),
            "promptDigest": item.get("promptDigest"),
            "submissionDigest": item.get("submissionDigest"),
            "submissionChanged": item.get("submissionChanged"),
        }
        for item in records
    ]
    return {
        "studyId": config.study_id,
        "configDigest": digest,
        "snapshotCommit": config.snapshot_commit,
        "scaffold": config.scaffold,
        "repeats": config.repeats,
        "budget": config.budget.model_dump(),
        "models": [
            {
                "id": model.id,
                "litellmModel": model.litellm_model,
                "endpointHost": model.endpoint_host,
                "extraBody": model.extra_body,
                "thinking": model.thinking,
                "outputConfig": model.output_config,
                "omitParams": list(model.omit_params),
                "streamResponses": model.stream_responses,
                "promptCaching": model.prompt_caching,
                "maxOutputTokens": model.max_output_tokens,
            }
            for model in reported
        ],
        "scheduledAttempts": len(reported) * (len(config.tasks) - len(exclusions.tasks)) * config.repeats,
        "recordedAttempts": len(records),
        "exclusions": exclusions.public(),
        "deviations": {
            **_deviations(root, records, kept, excluded_attempts),
            "excludedTasks": len(exclusions.tasks),
            "excludedRecordedAttempts": dropped,
        },
        "summary": summary["summary"],
        "perTask": summary["perTask"],
        "attempts": attempts,
    }


def _attempt_id(attempt: object) -> str:
    return str(attempt.get("attempt_id") if isinstance(attempt, dict) else attempt)


def _counted(attempt_id: str, models: set[str], excluded: set[str]) -> bool:
    return attempt_id.split("--", 1)[0] in models and attempt_id not in excluded


def _listed(path: Path, models: set[str], excluded: set[str]) -> int:
    if not path.is_file():
        return 0
    loaded = json.loads(path.read_text(encoding="utf-8"))
    attempts = loaded.get("attempts", []) if isinstance(loaded, dict) else []
    return sum(_counted(_attempt_id(attempt), models, excluded) for attempt in attempts)


def _deviations(
    root: Path, records: list[dict[str, Any]], models: set[str], excluded: set[str]
) -> dict[str, Any]:
    """Counts of everything that departs from one clean pass over the schedule.

    ``excluded`` holds the scheduled attempt ids of excluded tasks; they count nowhere.
    """
    voided = root / "voided-attempts"
    return {
        "voidedBeforeAnyModelRequest": {
            "proxyNameTooLong": _listed(voided / "VOIDED.json", models, excluded),
            "networkPoolExhausted": _listed(voided / "VOIDED-netpool.json", models, excluded),
            "setupTimeoutMislabelled": _listed(voided / "VOIDED-setup-timeout.json", models, excluded),
        },
        "voidedAfterProviderInterruption": _listed(
            voided / "VOIDED-provider-interrupted.json", models, excluded
        ),
        "outOfScopeAfterAmendment": sum(
            _counted(path.parent.name, models, excluded)
            for path in (root / "out-of-scope-attempts").glob("*/attempt.json")
        ),
        "adjudicated": dict(
            Counter(str(item["adjudication"]) for item in records if "nativeOutcome" in item)
        ),
        "rescoredAfterContextExhaustion": sum("rescoredAt" in item for item in records),
        "restartedGenerationStarts": sum(len(item.get("voidedGenerationStarts") or []) for item in records),
        "restartedAfterProviderInterruption": sum(
            sum(
                start.get("kind") == "provider-interrupted"
                for start in item.get("voidedGenerationStarts") or []
            )
            for item in records
        ),
        "voidedEvaluatorStarts": sum(len(item.get("voidedExecutions") or []) for item in records),
        "reevaluatedAttempts": sum("reevaluatedAt" in item for item in records),
    }


def _e2(
    paths: StudyPaths, config: StudyConfig, exclusions: Exclusions, excluded_attempts: set[str]
) -> dict[str, Any]:
    root = paths.data_root / "e2" / config.study_id
    selection = root / "selection.json"
    chosen = json.loads(selection.read_text(encoding="utf-8")) if selection.is_file() else None
    if chosen is not None and excluded_attempts:
        paired = chosen.get("successfulControls") or {}
        named = {*chosen["eligible"], *chosen["selected"], *paired, *filter(None, paired.values())}
        if stale := sorted(named & excluded_attempts):
            raise ValueError(
                f"{selection} names attempts of excluded tasks ({', '.join(stale)}); run e2 select again"
            )
    replays = []
    for path in sorted(root.glob("*/*/replay.json")):
        replay = json.loads(path.read_text(encoding="utf-8"))
        if replay["task"] in exclusions.tasks:
            continue
        replays.append(
            {
                "attempt": replay["attempt"],
                "task": replay["task"],
                "replay": replay["replay"],
                "score": replay["score"],
                "complete": replay["complete"],
                "passed": replay["passed"],
                "observations": dict(Counter(replay["cases"].values())),
            }
        )
    return {"selection": chosen, "replays": replays}


def export(
    paths: StudyPaths,
    config: StudyConfig,
    digest: str,
    out: Path,
    models: tuple[str, ...] = (),
    *,
    exclusions: Exclusions,
) -> list[Path]:
    excluded_attempts = {item.attempt_id for item in schedule(config) if item.task in exclusions.tasks}
    payloads = (
        # E0 describes the registered inventory, not one study, so no exclusion applies to it.
        ("e0-admission.json", _e0(paths)),
        ("e1-results.json", _e1(paths, config, digest, exclusions, excluded_attempts, models)),
        ("e2-interventions.json", _e2(paths, config, exclusions, excluded_attempts)),
    )
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in payloads:
        path = out / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written
