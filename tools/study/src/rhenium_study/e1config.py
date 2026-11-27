from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelCondition(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    litellm_model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key_file: Path
    extra_body: dict[str, Any] = Field(default_factory=dict)
    # Mark the conversation for provider-side prompt caching (Anthropic `cache_control`),
    # which Claude models only apply to explicitly marked messages.
    prompt_caching: bool = False
    # Sent as the request's max_tokens; litellm otherwise falls back to 4096 for an
    # Anthropic model it does not know, which truncates long thinking.
    max_output_tokens: int | None = Field(default=None, ge=1)
    # Sent as the request's top-level Anthropic `thinking` field (litellm's own argument,
    # explicitly allowed so drop_params cannot remove it). Through extra_body litellm nests
    # it under a literal "extra_body" key instead.
    thinking: dict[str, Any] | None = None
    # Sent as the request's top-level Anthropic `output_config` (for example
    # `{effort = "high"}`, which adaptive thinking takes instead of a token budget).
    output_config: dict[str, Any] | None = None
    # Sampling parameters the scaffold sets that this model must not receive: Rhenium's
    # ModelRunner always sends temperature 0, which a model with adaptive thinking rejects.
    omit_params: tuple[Literal["temperature", "top_p"], ...] = ()
    # Request every response as a stream and assemble it before the agent sees it. A proxy in
    # front of an endpoint can drop a request whose first byte misses its deadline, which a
    # non-streaming request to a model that thinks for minutes cannot meet.
    stream_responses: bool = False

    @model_validator(mode="after")
    def omitted_params_are_unique(self) -> Self:
        if len(set(self.omit_params)) != len(self.omit_params):
            raise ValueError(f"model {self.id} names an omitted parameter twice")
        return self

    @property
    def endpoint_host(self) -> str:
        host = urlsplit(self.base_url).hostname
        if not host:
            raise ValueError(f"model {self.id} has no endpoint host")
        return host


class Budget(_Strict):
    step_limit: int = Field(ge=1, le=1000)
    command_timeout_seconds: int = Field(ge=1)
    wall_time_limit_seconds: int = Field(ge=60)
    request_timeout_seconds: int = Field(ge=30)
    # End a generation once the model issues exactly the same commands this many times in a
    # row; the attempt is then recorded as failed without evaluation. None disables it.
    repeated_action_limit: int | None = Field(default=None, ge=2)


class StudyConfig(_Strict):
    """The frozen conditions of one study. Its digest is stamped on every attempt."""

    study_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    snapshot_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    scaffold: str
    repeats: int = Field(ge=1)
    schedule_seed: int
    agent_image: str
    budget: Budget
    models: tuple[ModelCondition, ...] = Field(min_length=1)
    tasks: tuple[str, ...] = Field(min_length=1)
    e2_selection_rule: str = Field(min_length=1)
    e2_max_cases: int = Field(ge=1)
    # Games whose engine this host cannot run. Their attempts are generated here under
    # the same conditions, frozen, and evaluated later on a host that has the engine
    # (`e1 export-deferred` / `e1 import-evaluations`).
    deferred_evaluation: tuple[str, ...] = ()

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> Self:
        if len({model.id for model in self.models}) != len(self.models):
            raise ValueError("model condition ids must be unique")
        if len(set(self.tasks)) != len(self.tasks):
            raise ValueError("tasks must be unique")
        return self

    @classmethod
    def load(cls, path: Path) -> tuple[Self, str]:
        raw = path.read_bytes()
        return cls.model_validate(tomllib.loads(raw.decode("utf-8"))), hashlib.sha256(raw).hexdigest()
