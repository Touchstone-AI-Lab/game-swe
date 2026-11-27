# Decision requested: satisfy the existing frontend Node requirement

The approved Node 22.19.0 archive passed its published hash check. The unchanged
frontend lock contains jsdom 30.0.1, whose declared Node requirement is
`^22.22.2 || ^24.15.0 || >=26.0.0`. Dependency restoration completed with installation
scripts disabled, but npm reported `EBADENGINE`. Frontend checks have not been
claimed as passing in that unsupported environment.

The earlier [tool request](CHECK-TOOLS-REQUEST-v1.md) specified 22.19.0 and said
"no dependency/version substitution is authorized on failure." This separate
decision authorizes a new check-only copy; it does not overwrite that tool or
change any host, game, existing Python environment, dependency lock or permission.

## Concrete operation

- Download `https://nodejs.org/dist/v22.22.2/node-v22.22.2-linux-x64.tar.xz`.
- Verify SHA-256
  `88fd1ce767091fd8d4a99fdb2356e98c819f93f3b1f8663853a2dee9b438068a`, read from
  the official versioned `https://nodejs.org/dist/v22.22.2/SHASUMS256.txt`.
- Extract only under `/home/psy/balatro-linux-v1/checks-v3/node-v2/`, with archive
  path/link confinement. Bound the download to 180 seconds / 100 MB.
- Reuse the already restored, unchanged locked frontend dependencies and empty
  task-local npm configuration. Do not execute installation lifecycle hooks.
- Run lint, single-worker tests and production build in the independent source
  copy. Keep logs, tool identities and source/output hashes in ignored evidence.

Node 22.19.0 and its original receipts remain intact. No system installation,
global PATH change, dependency upgrade, game, account login or model run is included.
The implementation is prepared as the operator-local
`.test-state/repository-checks-v3/prepare-node-v2.py` and awaits this decision.
