from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .safe_files import secure_read_bytes

PROTOCOLS = {
    2: ("rhenium-rimworld-private-v2", "rhenium-rimworld-observer-v2"),
    3: ("rhenium-rimworld-private-v3", "rhenium-rimworld-observer-v3"),
}

_CASE_ID = r"^[a-z0-9][a-z0-9-]*$"
_FIXTURE = r"^[A-Z][A-Za-z0-9]*$"
_NAME = r"^[A-Za-z][A-Za-z0-9]*$"


class AssertionMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def_name: str = Field(alias="defName", pattern=r"^[A-Za-z][A-Za-z0-9]*$")
    count: int = Field(gt=0)


class AssertionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    channel: str = Field(pattern=_NAME)
    entries: list[AssertionMaterial]

    @model_validator(mode="after")
    def material_names_are_unique(self) -> Self:
        names = [entry.def_name for entry in self.entries]
        if len(names) != len(set(names)):
            raise ValueError("assertion output material names must be unique")
        return self


class AssertionFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(pattern=_NAME)
    value: str = Field(min_length=1, max_length=160)


class AssertionExpected(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    facts: list[AssertionFact]
    outputs: list[AssertionOutput]

    @model_validator(mode="after")
    def names_are_unique(self) -> Self:
        fact_names = [fact.name for fact in self.facts]
        channels = [output.channel for output in self.outputs]
        if len(fact_names) != len(set(fact_names)):
            raise ValueError("assertion expected fact names must be unique")
        if len(channels) != len(set(channels)):
            raise ValueError("assertion expected output channels must be unique")
        return self


class AssertionCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(pattern=_CASE_ID)
    fixture: str = Field(pattern=_FIXTURE)
    gate: bool
    scalars: list[str]
    expected: AssertionExpected

    @model_validator(mode="after")
    def scalar_names_are_unique(self) -> Self:
        if any(re.fullmatch(_NAME, name) is None for name in self.scalars):
            raise ValueError("assertion scalar names are invalid")
        if len(self.scalars) != len(set(self.scalars)):
            raise ValueError("assertion scalar names must be unique")
        return self


class AssertionWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    submission_shape: int = Field(alias="submissionShape")
    engine_assertions: int = Field(alias="engineAssertions")


class AssertionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[2, 3] = Field(alias="schemaVersion")
    protocol: Literal[
        "rhenium-rimworld-private-v2", "rhenium-rimworld-private-v3"
    ]
    adapter: Literal[
        "rhenium-rimworld-observer-v2", "rhenium-rimworld-observer-v3"
    ]
    task_key: str = Field(
        alias="taskKey",
        pattern=r"^rimworld/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$",
    )
    weights: AssertionWeights
    cases: list[AssertionCase] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def contract_is_coherent(self) -> Self:
        case_ids = [case.id for case in self.cases]
        fixtures = [case.fixture for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("assertion case IDs must be unique")
        if len(fixtures) != len(set(fixtures)):
            raise ValueError("assertion fixtures must be unique")
        if (self.protocol, self.adapter) != PROTOCOLS[self.schema_version]:
            raise ValueError("RimWorld private and observer protocols do not match the schema")
        if self.schema_version == 2 and len(self.cases) != 38:
            raise ValueError("legacy RimWorld protocol v2 requires exactly 38 cases")
        if (
            self.weights.submission_shape != 10
            or self.weights.engine_assertions != 90
        ):
            raise ValueError("RimWorld assertion weights must remain 10/90")
        if sum(case.gate for case in self.cases) != 2:
            raise ValueError("RimWorld private protocols require exactly two gates")
        if self.schema_version == 3 and not (self.cases[0].gate and self.cases[-1].gate):
            raise ValueError("protocol v3 gates must bracket every behavior fixture")
        return self

    @property
    def collector(self) -> str:
        return f"rhenium-rimworld-supervisor-v{self.schema_version}"

    @property
    def case_names(self) -> tuple[str, ...]:
        return tuple(case.id for case in self.cases)

    @property
    def by_id(self) -> dict[str, AssertionCase]:
        return {case.id: case for case in self.cases}

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(by_alias=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def rubric_hash(self) -> str:
        return f"sha256:{hashlib.sha256(self.canonical_bytes()).hexdigest()}"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate assertion manifest key: {key}")
        result[key] = value
    return result


def load_assertion_manifest(pack_root: Path, task_id: str) -> AssertionManifest:
    relative = f"private/harbor/{task_id}/tests/assertions.json"
    raw = secure_read_bytes(pack_root, relative, maximum=1_000_000)
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite assertion manifest value: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("assertion manifest is malformed") from error
    if not isinstance(value, dict):
        raise ValueError("assertion manifest must be an object")
    return AssertionManifest.model_validate(value)


def generated_dispatch_source(manifest: AssertionManifest) -> bytes:
    rows = "\n".join(
        "            new AssertionDispatch("
        f'"{case.id}", {case.fixture}, {str(case.gate).lower()}),'
        for case in manifest.cases
    )
    return (
        "// Generated from private assertions.json; do not edit.\n"
        "namespace Rhenium.RimWorld.Verifier\n"
        "{\n"
        "    public static partial class VerifierBootstrap\n"
        "    {\n"
        "        private static readonly AssertionDispatch[] AssertionPlan =\n"
        "        {\n"
        f"{rows}\n"
        "        };\n"
        "    }\n"
        "}\n"
    ).encode()
