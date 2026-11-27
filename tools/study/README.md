# rhenium-study

Repository-maintenance tooling for controlled studies over the registered benchmark
tasks: contract admission (E0), the frozen model-by-task study (E1) and interventions
on observed integration failures (E2). It never takes part in scoring and is not
packaged with any plugin.

All study data (Hub state, control trees, attempts, trajectories, logs, reports) lives
under `RHENIUM_STUDY_DIR`, default `~/Projects/game-swe-study`, and must be outside the
repository. Clause maps and control assets are private maintenance material under
`benchmarks/<pack>/private/study-controls/<task>/`; they are never copied into an
attempt or a model workspace.

The inventory includes all ten Minecraft repair tasks of core catalog 0.2.0 and the
five Minecraft construct tasks. Their full evaluations require the pinned Paper
1.21.11 build 132 runtimes, prepared through `official-download`, and the operator's
EULA acceptance records in the selected Hub state. Preparation is a separate
operator action; the study seeds immutable runtime records and performs no downloads
or licence acceptance while evaluating submissions.

Balatro's ten frozen v0.2 tasks are registered on their reviewed Linux container
runtime. Each reference is the pack's frozen gold control (`reference_tree`), and the
frozen mutants are reused through `pack:` overlays. The evaluator publishes anonymous
`check-<n>` rows, so a clause map lists them as `position:<n>` cases whose `note` is the
scenario's case name. That order comes from recorded engine results; for
`durable-charge-v2` and `shop-price-coherence-v2` it differs from the frozen `required`
list. Four tasks have a frozen independent alternative. The other six use an
`alternative-public` control written from the public contract without reading the gold
control. A frozen mutant that fails target and preserved cases at once fits no control
kind and stays out of the manifest; the plugin's own control matrix still covers it.
E0 admitted all ten tasks on 62 real-engine controls, and four are qualified for the joint
compatibility analysis.

That runtime executes only source-reviewed bytes, so a Balatro E1 study lists `balatro` in
`deferred_evaluation`. Generation leaves each attempt pending. The operator reads the
exact submission, records its seal with `python -m rhenium_balatro.container_operator
review`, evaluates it with `rhenium run`, and scores the output with `e1 import-evaluations`.
Evaluations run one at a time. An incomplete run leaves the runtime's halt marker in
place, and that artifact then refuses further evaluations and reviews; see the
[container guide](../../docs/games/balatro-container-v1.md#study-attempts). None of this is
an E1 model calibration of the pack.

`e1 review-balatro` can stand in for the reading. For each Balatro attempt of a kit from
`e1 export-deferred`, it scans every file under the frozen submission's `starter/` with the
static policy `balatro-static-review-v1`, and only when the policy finds nothing does it run
the plugin's unchanged `container_operator review` to record the seal:

```sh
rhenium-study e1 review-balatro --config study.toml --kit <kit> \
  --pack benchmarks/balatro --state <operator-state> --cache <operator-cache> \
  --artifact <runtime-verify.json> [--evaluate]
```

The policy parses Lua comments and strings, then flags the capabilities a source review
refused: `io`, `debug`, `package`, `require`, `load`, `loadstring`, `loadfile`, `dofile`,
`setfenv`, `getfenv`, `_G`, `_ENV`, `ffi`, `jit`, `socket` and native file access;
`os` beyond reading the clock; `love` beyond its timer and math modules, since the observer
hooks the rest; `string.dump` and any `dump`, `getenv` or `popen` field;
`SMODS.load_file` of anything but a sealed file named by a plain literal; and every
reference to the observer, the guard or the BalatroBot harness (`BB_` and `POC_` names,
`poc.runtime`, `poc_guard`, ...). A file other than Lua or JSON, a file that does not
parse and a symbolic link are findings too. Each attempt's decision, with its file
hashes and findings, is written to `attempts/<id>/auto-review.json` in the kit. An
attempt with a finding is not sealed: the operator reads it as before, and the command
exits 2. The plugin itself is not changed, so its prepared runtime and its existing
review records stay valid.

The policy is a guard for honest submissions, not a sandbox. It cannot tell whether code
special-cases a scoring scene or writes game state to fake a result, and deliberately
obfuscated code can reach a capability without naming it. Before use it cleared every
submission that an operator had read and accepted, and the ten public starters, and the
unit tests cover each rule.

With `--evaluate` the command then runs `rhenium run <task> <submission> --profile full`
once for each sealed attempt without a result, one at a time, and writes
`attempts/<id>/result-1.json`. It never retries: at the first incomplete run it stops and
exits 4, because the artifact is halted until the operator has diagnosed it. Score the
results with `e1 import-evaluations` as usual.

A seal belongs to one prepared artifact: the plugin keeps it in that artifact's operator
state, so each `auto-review.json` records the identity of the artifact it was sealed on.
After a halt has been recovered with a new artifact, run the command again with the new
artifact's verify output. It seals again every attempt that has no result yet, and
`--evaluate` runs only attempts sealed on the artifact it was given. An attempt that
already has a result is never sealed again.

## E0: contract admission

```sh
rhenium-study tasks                                   # the registered repair and construct tasks
rhenium-study seed --operator-database <state.sqlite> # copy prepared-runtime records only
rhenium-study e0 baseline [task-key...]               # unchanged starter + reference
rhenium-study e0 draft-maps [task-key...]             # draft clause maps from the baseline
rhenium-study e0 check-maps [task-key...]
rhenium-study e0 run [task-key...] [--only <control>]
rhenium-study e0 flag                                 # mark over-constrained cases from records
rhenium-study e0 report                               # reports/E0.md + E0-admission.json
```

- `clause-map.json` maps every public clause to the frozen cases that are evidence for
  it. A case is `target`, `preserved` (it already passes in the unchanged starter),
  `runtime-sentinel`, `setup` or `static`; a clause is `asserted`, `weak` or `unasserted`.
- `manifest.tsv` declares controls beyond the implicit starter and reference:
  `target-negative`, `compat-negative` (a preserved contract broken while every target
  case still passes) and `alternative`. Each kind has one admissible outcome, checked
  from name-level engine observations.
- An `alternative-strict-reading*` control is a valid implementation of the public exam
  that a private assertion rejects. It never excludes the task: `e0 flag` marks the cases
  it does not pass as `over_constrained`, and those cases stay out of the audited target
  and preserved sets. Assertions are never edited.
- Admission needs an admissible starter, reference, target-negative and alternative.
  Joint-compatibility qualification additionally needs an audited preserved case and an
  admissible compat-negative. No agent score is consulted.

Evaluation goes through an isolated study Hub (runtime records are seeded from the
operator Hub; provider sessions are never copied). GMod Addons, which has no managed
runtime, is evaluated in its local pinned-server image without network.

Each study process constructs its Hub once and reuses it for every later preparation and
evaluation, so a lane loads the task catalogs when it first needs its Hub and the benchmark
packs must not change while lanes run. Constructing a Hub rebuilds every starter workspace in the
shared Hub state, so it runs under the host-wide `locks/hub-startup.lock`; preparing an
attempt and copying a starter into a control tree hold the same lock and never see a
half-written rebuild. Attempt preparation is also serialized by
`locks/attempt-prepare.lock`. At most four evaluations of one game pack run at once on the
host (`locks/engine-<game>-<pack>-<slot>.lock`); a further one waits for a free slot.

## E1: the frozen study

```sh
rhenium-study e1 image --config study.toml   # build the digest-pinned agent image
rhenium-study e1 plan  --config study.toml
rhenium-study e1 run   --config study.toml --lane 0 --lanes 4
rhenium-study e1 adjudicate --config study.toml
rhenium-study e1 report --config study.toml
```

`study.toml` freezes models, scaffold, budgets, repeats, the schedule seed, the task
list, the snapshot commit and the E2 selection rule; its SHA-256 is stamped on every
attempt. Each attempt is one generation in a capability-free container on an internal
Docker network whose only exit is a CONNECT proxy allowlisting the model endpoint, then
a frozen copy of the submission is evaluated. An evaluator execution is classified as
resolved, failed, invalid or unattributed in the protocol's order, and only an invalid
or unattributed execution gets one retry with the same source. Records keep the prompt,
starter and submission digests, provider token usage, the termination reason and a
`P`/`F`/`U` observation for every frozen case, plus the native verdict and the audited
outcome side by side. An execution whose evaluator container was never created (the Hub
run's runtime log records a `docker create` that timed out, the plugin reports that
its isolated verifier could not be created, or RimWorld's private failure record for the
evaluation says its prepared runtime failed verification against the current pack, which
it checks before creating any container) observed nothing about the submission: it is
kept under `executions/voided/`, listed in `voidedExecutions`, and run again after a
pause, at most three times, without using up the retry. `e1 reevaluate --config
study.toml` applies the same rule to executions already recorded; it evaluates only the
frozen submission and generates nothing. A finished attempt is never repeated; create `STOP.<study_id>` in the data
directory to stop lanes between attempts.

Tasks leave a running or finished study through `task-exclusions.json` in the study's
directory (`e1/<study_id>/`, beside `attempts/`), so `study.toml` stays byte-identical
and every recorded digest still matches:

```json
{"studyId": "<study_id>", "configDigest": "<SHA-256 of study.toml>",
 "amendments": [{"tasks": ["<game>/<pack>/<task>"], "reason": "...",
                 "decidedAt": "YYYY-MM-DD", "decidedBy": "..."}]}
```

Every `e1`, `e2` and `paper-export` command checks the file when it loads the
configuration and stops if anything at that path cannot be read, has a missing, unknown
or empty field, names another study or configuration digest, excludes a task the
configuration does not list, or excludes a task twice. With or without the file, it also
stops when a configured task is neither registered nor excluded. `e1 plan` reports the
excluded and remaining attempts. `e1 run` skips excluded attempts; the schedule is still
drawn from the full task list, so every other attempt keeps its order number and lane.
The records of excluded tasks stay on disk untouched, and `adjudicate`, `report`,
`reevaluate` without `--attempt`, `export-deferred` and `e2 select` leave them out, so
`adjudicate` rewrites `adjudication.json` without their decisions and refuses a manual
adjudication entry for one as not admissible. `rescore`, `reevaluate --attempt`,
`import-evaluations` and `e2 replay` refuse them before acting on any named attempt.
`report` writes the amendments into `summary.json`. `paper-export` leaves excluded tasks
out of `perTask`, `attempts`, `summary` and the deviation counts. It counts
`scheduledAttempts` over the remaining tasks and records the amendments as `exclusions`,
plus two integers: `deviations.excludedTasks` and `deviations.excludedRecordedAttempts`,
the recorded (not pending) attempts of excluded tasks for the reported models. It refuses
an E2 selection that still names an excluded attempt. E0 covers the registered inventory,
not a study, and is unaffected.

A generation start that the model never answered (the isolated network or proxy could not
be assembled, the run errored before the proxy opened one connection to the endpoint, or
the endpoint refused every request, for example with a rate limit or an unavailable model,
so the agent never began its second step) sampled nothing, so it is kept under `voided/`
in the attempt directory and started again, at most three starts in all. Once the model
has answered there is no second generation:
a run that then ends with a scaffold error or a provider error the model's own requests can
cause is recorded as `invalid`, its partial tree is not scored, and both obligation sets
stay unknown. A generation the provider stopped serving after the model had answered (a
rate limit, an unavailable service, a dropped connection, a timeout or a server error) is
also voided: the workspace is prepared again from the starter and the generation starts
over, within the same three starts. The trigger does not depend on the model's work.
Attempts recorded as `invalid` for that reason before this rule are moved to
`voided-attempts/` and listed in `VOIDED-provider-interrupted.json`, then generated again. Container names are
hashes of the attempt id and a per-start token because the proxy's name is its DNS label
(63 characters at most). Each start first removes every container and network carrying
that attempt's label, and takes fresh names, because a congested daemon can still be
removing a failed start's proxy when the next start begins. The agent retries a
failed model request up to 30 times with exponential backoff (4 to 60 seconds), so a
provider throttling burst of up to about 25 minutes does not end a generation; the wait
counts against the wall-clock budget.

A model's `prompt_caching = true` marks the newest message of every request with
Anthropic's `cache_control` (mini-swe-agent's `default_end`), because Claude models reuse
a cached prefix only when it is marked. It changes billing and latency, not the messages.
`max_output_tokens` is sent as each request's `max_tokens`; without it litellm sends 4096
for an Anthropic model missing from its model map, which cuts long thinking short.
`thinking` is sent as the request's top-level Anthropic `thinking` field: it is passed as
litellm's own argument and explicitly allowed, because under `drop_params` litellm drops it
for an Anthropic model missing from its model map. On the Anthropic route litellm sends
`extra_body` as a literal nested `extra_body` key, so settings placed there reach the model
only if the endpoint unwraps that key. `output_config` is therefore its own field: it is
passed as a top-level litellm argument and sent as the request's top-level Anthropic
`output_config`. `omit_params` names sampling parameters (`temperature`, `top_p`) the
model must not receive; Rhenium's ModelRunner always sets `temperature` to 0, and litellm
removes each named parameter before the request (`additional_drop_params`). Other models
keep temperature 0, and on litellm's `openai/` route their `extra_body` keys are merged
into the top level of the request. Claude Opus 5 on the direct Anthropic API
(`base_url = "https://api.anthropic.com"`, without `/v1`) needs both fields: it rejects
`thinking.type = "enabled"`, and with adaptive thinking it rejects any temperature but 1.

`stream_responses = true` requests every response as a stream and assembles the chunks into
the response object the agent would otherwise receive. It changes the transport, not the
messages. Without it, a proxy that drops a request whose first byte misses its deadline
drops every non-streaming request to a model that thinks for longer than that: the retry
meets the same deadline, so the generation stays on that step until the container's
wall-clock limit ends it, and only the tasks with short requests finish. Cloudflare answers
such a request with error 524 after about 125 seconds on `gateway.agentsky.dev`. A stream
that ends without a finish reason counts as a failed request and is retried.

```toml
[[models]]
id = "claude-opus-5"
litellm_model = "anthropic/claude-opus-5"
base_url = "https://api.anthropic.com"
api_key_file = "<key file>"
thinking = { type = "adaptive", display = "summarized" }
output_config = { effort = "high" }
omit_params = ["temperature"]
prompt_caching = true
max_output_tokens = 64000
```

Because the pinned litellm's model map does not list `claude-opus-5`, litellm also sends
the `anthropic-beta: effort-2025-11-24` header with these requests. Attempt records keep
these fields in `modelCondition`, and `paper-export` lists them as `outputConfig`,
`omitParams` and `streamResponses`.

DST and Palworld prompts tell the agent to run `python -m rhenium_<game>.public_check`. The
agent's shell does not inherit the runner's environment, so for those two games the shell
gets `PYTHONPATH` with that plugin, `rhenium` and its dependencies; other games' shells are
unchanged. Before 2026-09-25 the command failed with `ModuleNotFoundError` unless the agent
worked out the module path itself.

A game whose engine this host cannot run (Palworld's dedicated server needs Windows) is
listed in the study's `deferred_evaluation`. Its attempts are generated here under the same
frozen conditions, their submissions are frozen, and the record is `pending-evaluation`:
it enters no result. `e1 export-deferred --config study.toml --out <kit>` packs every
pending submission with a manifest, a README for the evaluating operator and
`evaluate.ps1`/`evaluate.sh`, which run the repository's own `rhenium run <task> <submission>
--profile full` once per attempt (plus the protocol's single retry after an incomplete run)
at the study's snapshot commit. `e1 import-evaluations --config study.toml --kit <kit>
--host "<host and engine build>"` checks that the kit belongs to this configuration and
scores the returned outputs with the same classification, retry rule and verdict as a
local evaluation; the evaluating host is recorded on every execution.

`e1 adjudicate` closes an unattributed attempt only through a declared rule over evidence
the trusted verifier wrote itself. Two rules exist, for Stardew and for L4D2: no case
beyond the source gates may have been observed, and every execution's verifier log must
carry the verifier's own build-failure line (`submission build failed`, or
`SUBMISSION_FAILED: SourcePawn compile failed`) and no verifier-fault line
(`harness build failed`, `INVALID_ENVIRONMENT:`); the attempt then counts as failed. Decisions live in `adjudication.json`
beside the ledger, the native outcome stays on the record as `nativeOutcome`, and case
observations are untouched, so unreached cases remain unknown in the joint analysis.
An attempt no rule covers can be closed through `adjudication-manual.json` beside the
ledger: each entry names the attempt, the reviewer and a written rationale, may only
turn an unattributed attempt into a failed one, and is reported as `manual-review`.
A study's budget may set `repeated_action_limit`: when the model issues exactly the same
commands that many times in a row, the runner ends the generation with exit status
`RepeatedActionLoop`, and the attempt is recorded as `failed` (termination reason
`repeated-action-loop`) without being evaluated. Budgets without the field are unchanged.
`RHENIUM_STUDY_ENGINE_SLOTS` sets the number of evaluation slots per game pack (default 4);
every process sharing a data directory should use the same value.
A generation that ends because the conversation outgrew the model's context is a budget
termination of the frozen scaffold, not an infrastructure error: its tree is scored like
any other candidate (`e1 rescore` scores one that was recorded before this rule).
The rules were written with AI assistance and have not had independent human review.

The agent container holds text and shell tools only (no game, verifier, compiler or
credentials). This is an operator-enforced condition, not a sandbox for hostile code.

## E2: interventions

```sh
rhenium-study e2 select --config study.toml
rhenium-study e2 replay --config study.toml --attempt <id> [--patch repair.patch]
```

Selection applies the rule frozen in `study.toml` (all target-satisfied,
contract-violated attempts; stratified by source family above the cap) and pairs each
case with a successful control from the same task when one exists. A replay evaluates
the frozen submission, unchanged or with one intervention patch, under the same
evaluator identity; failed interventions are kept.

The Minecraft inventory closure check also requires clause-map versions and the
complete server/unit case sets to match each pack's catalog. Construct maps had
kept version 1.1.0 while their cases and runtime had advanced to catalog 1.3.0;
they now record 1.3.0. Older control records retain their original version field.
Current admission requires fresh version-matched records rather than silently
relabeling those historical records.
