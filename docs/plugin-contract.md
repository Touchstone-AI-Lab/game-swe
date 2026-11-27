# Plugin contract

A game integration is an independent Python distribution. It depends on
`rhenium`, owns its engine dependencies, and registers one entry point:

```toml
[project.entry-points."rhenium.benchmarks"]
example-game = "rhenium_example.plugin:ExampleBenchmarkPlugin"
```

Entry-point discovery is the only supported loading mechanism.

Licensed-content authentication is a separate extension point so one account session
can serve multiple game plugins without adding provider semantics to core:

```toml
[project.entry-points."rhenium.auth_providers"]
steam = "rhenium_steam.provider:SteamAuthProvider"
```

An auth provider exposes a stable descriptor and implements interactive login,
session validation/refresh, and licensed-source acquisition:

```python
class AuthProvider(ABC):
    descriptor: AuthProviderDescriptor

    def login(
        self,
        account_alias: str,
        *,
        challenge: ChallengeCallback,
        progress: ProgressCallback,
    ) -> AuthSession: ...

    def validate(self, session: AuthSession) -> AuthSession: ...

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: ProgressCallback,
    ) -> AuthSession: ...
```

The core treats the source and session secret as provider-owned opaque objects.
Providers return refreshed sessions but must never expose their secret through a
view, progress message, challenge, operation result, or artifact.

## Descriptor and context

Every `BenchmarkPlugin` exposes a `PluginDescriptor` with stable plugin/game
IDs, display name, semantic version, and capabilities. The Hub supplies a
read-only `BenchmarkContext` for each pack:

```python
PluginDescriptor(
    id="example-game",
    game_id="example-game",
    name="Example Game",
    version="0.6.0",
    capabilities=("static-analysis", "headless-runtime"),
)

BenchmarkContext(
    project_root=project_root,
    pack_root=pack_root,
    state_dir=state_dir,
    cache_dir=cache_dir,
)
```

Plugins read catalogs, private tests, and authored exams from `pack_root`.
Generated files belong in `state_dir` or `cache_dir`.

## Required hooks

```python
def load_catalog(pack_root: Path, catalog_path: str) -> BenchmarkCatalog: ...
def create_evaluator(context: BenchmarkContext) -> EvaluationBackend: ...
```

## Evaluation security mode

Plugin evaluators implement the existing local engine contract and do not choose the host
security policy. `honest` is the compatibility default for development, references and trusted
submissions. Explicit `untrusted` evaluation is routed by core through an independently
installed `rhenium.evaluation_hosts` provider. If a provider, immutable image identity or any
required proof is missing, core returns an incomplete non-passing result and must not invoke the
local evaluator as a fallback.

The guest provider wrapper must run the plugin's evaluator and apply
`sanitize_anonymous_result()` before returning its bounded run-ID/nonce-bound result envelope.
Plugins must not put host-provider or hypervisor branches in game code, and host providers must
not duplicate game evaluator logic. The executable host contract and threat model are in
[Disposable evaluation hosts](disposable-evaluation-hosts.md).

The evaluator contract is:

```python
def evaluate(
    submission: Path,
    task: Any,
    profile: str = "full",
    runtimes: dict[str, RuntimeArtifact] | None = None,
) -> dict[str, Any]: ...

def runtime_status() -> dict[str, Any]: ...
```

Packs that require a separately prepared licensed runtime select a generic
`runtimes.json` from `benchmark.json`. The game plugin implements
`create_runtime_builder(context, spec)` while the auth provider validates and acquires
the opaque provider-specific `source`. Complete profiles receive only immutable
`RuntimeArtifact` values; evaluation never prepares a missing runtime implicitly.

The builder contract is:

```python
class RuntimeBuilder(ABC):
    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]: ...
    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: RuntimeProgress,
    ) -> RuntimeArtifact: ...
    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]: ...
    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None: ...
```

`RuntimeArtifact.identity` identifies immutable local content; metadata contains
only non-secret evaluator inputs. When a legitimate client-bound step is required,
the builder may raise `RuntimeActionRequired` and let the operator rerun explicit
preparation afterward. The full catalog schema, lifecycle, security rules, and
examples are in [Managed authentication and runtimes](managed-runtimes.md).

Every result must contain `score`, `complete`, `passed`, `checks`, and
`runtime_log`. Plugin-specific fields are preserved. The core rejects a result
that passes while incomplete.

## Profiles

Plugins expose `EvaluationProfile` values. The baseline contract provides:

| Profile | Meaning | Complete eligible |
| --- | --- | --- |
| `core` | Engine-independent or reduced diagnostics | No |
| `full` | All assertions required by the plugin rubric | Yes |

A plugin may override labels, add profiles, or choose another default. Unknown
profiles fail before a job is scheduled. A complete-eligible profile still
needs the evaluator to confirm that required assertions actually ran.

## Optional hooks

Plugins may customize public prompts, starter materialization, anonymous exam
bundles, agent system guidance, safe non-secret environment variables, public
task metadata, completion-report fields, and anonymous-result sanitization.
Plugin-specific runtime protocols must remove private payloads, case-level
details, nonces, markers, raw output, internal commands/paths, and assertion
evidence in `sanitize_anonymous_result`; the Hub then applies game-neutral task
and path redaction. None of these hooks may expose a canonical task key, pack
path, private assertion, or secret to an anonymous attempt.

## Failure rules

- Import failures affect only the failed plugin.
- Missing runtimes are reported as degradations, not global startup failures.
- Catalog and evaluator asset paths must remain below `pack_root`.
- Runtime failures fail closed; incomplete evaluations cannot pass.
- Auth session secrets never cross into plugin prompts, public attempts, or API views.
- Plugins must not write into benchmark packs.
- A plugin cannot register a game ID already owned by another plugin.

## Ownership

A normal game contribution changes only:

```text
plugins/<game>/
benchmarks/<pack>/
docs/games/<game>.md
```

Shared core changes require contract tests using at least two independently
packaged plugins.
