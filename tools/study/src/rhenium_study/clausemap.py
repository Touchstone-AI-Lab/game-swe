from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["target", "preserved", "runtime-sentinel", "setup", "static"]
ClauseStatus = Literal["asserted", "weak", "unasserted"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseEntry(_Strict):
    """One frozen evaluator case and the obligation set it is evidence for.

    ``target`` is the requested change. ``preserved`` is a contract that already
    holds in the unchanged starter. ``overlap`` records a case that is evidence
    for both; it stays in its primary role and is never silently partitioned.
    ``runtime-sentinel`` and ``setup`` prove the fixture ran. ``static`` is a
    source gate (files, syntax, depth) that belongs to delivery, not to either set.
    """

    id: str = Field(min_length=1)
    role: Role
    clauses: tuple[str, ...] = ()
    overlap: bool = False
    # Set from engine evidence: a valid implementation of the public exam (the
    # strict-reading alternative) does not pass this case. The assertion is left
    # untouched; the case is only kept out of the audited obligation sets.
    over_constrained: bool = False
    note: str = ""


class ClauseEntry(_Strict):
    id: str = Field(min_length=1)
    anchor: str = Field(min_length=1, description="Where the clause is in the public exam.")
    status: ClauseStatus
    note: str = ""


class ClauseMap(_Strict):
    task: str
    task_version: str
    exam: str
    cases: tuple[CaseEntry, ...] = Field(min_length=1)
    clauses: tuple[ClauseEntry, ...] = Field(min_length=1)
    excluded_clauses: tuple[str, ...] = ()
    known_issues: tuple[str, ...] = ()

    @model_validator(mode="after")
    def references_are_consistent(self) -> Self:
        case_ids = [case.id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("clause map lists a case twice")
        clause_ids = [clause.id for clause in self.clauses]
        if len(set(clause_ids)) != len(clause_ids):
            raise ValueError("clause map lists a clause twice")
        known = set(clause_ids)
        for case in self.cases:
            if not set(case.clauses) <= known:
                raise ValueError(f"case {case.id} cites an unknown clause")
            if case.role in {"target", "preserved"} and not case.clauses:
                raise ValueError(f"case {case.id} is evidence for no public clause")
        covered = {clause for case in self.cases for clause in case.clauses}
        for clause in self.clauses:
            if clause.status == "unasserted" and clause.id in covered:
                raise ValueError(f"clause {clause.id} is marked unasserted but has a case")
            if clause.status != "unasserted" and clause.id not in covered:
                raise ValueError(f"clause {clause.id} has no case; mark it unasserted")
        if not set(self.excluded_clauses) <= known:
            raise ValueError("an excluded clause is not in the clause list")
        return self

    def case_ids(self, *roles: Role, audited: bool = False) -> list[str]:
        """Case ids by role; ``audited`` leaves out cases shown to be over-constrained."""
        return [
            case.id
            for case in self.cases
            if (not roles or case.role in roles) and not (audited and case.over_constrained)
        ]

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
