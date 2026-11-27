# palworld/core/server-rule-ballot: clause map provenance

Drafted on 2026-09-24 by `rhenium_study.mapgen` from the task's frozen case lists,
not from engine runs: the hidden plain-Lua cases are the `run(...)` names in
`hidden/server-rule-ballot.lua`, the dedicated-server cases are the `ctx:case(...)` names in
`server/server-rule-ballot.lua`, and the integration gates are the catalog's `integration_checks`.
This is a construction task with an empty starter, so every executed case is a
`target` (linked to one `request` clause, the exam body), the source-pattern gates
are weak `integration:*` evidence, and required-files, lua-syntax and
implementation-depth are delivery gates (`static`).

Cases: {'static': 3, 'target': 16}.

Palworld's dedicated-server layer runs only on Windows, so no starter or reference
baseline was recorded on the study host and E0 cannot admit this task there; its
E1 attempts are evaluated on a Windows host through the deferred-evaluation kit.
Checked by the maintaining AI agent (not independently human-reviewed).
