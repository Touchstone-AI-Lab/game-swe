from __future__ import annotations

import math
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationReport(BaseModel):
    """Minimum cross-game result contract; plugin-specific fields are preserved."""

    model_config = ConfigDict(extra="allow")

    score: float = Field(ge=0)
    complete: bool
    passed: bool
    checks: list[dict[str, Any]]
    runtime_log: str = ""

    @field_validator("score")
    @classmethod
    def score_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("evaluation score must be finite")
        return value

    @model_validator(mode="after")
    def passing_report_must_be_complete(self) -> Self:
        if self.passed and not self.complete:
            raise ValueError("an incomplete evaluation cannot pass")
        return self


def normalize_evaluation(value: dict[str, Any]) -> dict[str, Any]:
    return EvaluationReport.model_validate(value).model_dump(mode="python")
