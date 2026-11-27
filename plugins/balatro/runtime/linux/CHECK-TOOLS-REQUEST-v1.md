# Decision requested: isolated missing-check tools

Status: proposal only; no Node/ShellCheck archive has been downloaded or executed.

The complete Ruff check now passes, and Mypy passes 386 source files with the
approved six-copy exception. Full pytest is running. The formerly missing shell
scripts were excluded by sparse checkout; they are now materialized from the
unchanged HEAD. No tracked benchmark content was edited.

WSL has no Node, npm, ShellCheck, Nix or devenv, including the usual user-local
locations. Windows has Node 22.19.0/npm 11.12.1. To validate the Linux branch's
frontend and shell checks in the same OS as CI, this proposal adds portable tools
only beneath `/home/psy/balatro-linux-v1/checks-v3/`. It installs no system package,
service, daemon, global PATH setting or new container and changes no existing venv.

## Exact acquisition

1. Node Linux x64 22.19.0 from
   `https://nodejs.org/dist/v22.19.0/node-v22.19.0-linux-x64.tar.xz`.
   SHA-256 from the official versioned SHASUMS256.txt:
   `c0649af18e6a24f6fe5535a3e86b341dd49a8e71117c8b68bde973ef834f16f2`.
2. ShellCheck 0.9.0-1 amd64, matching the available Ubuntu 24.04 package metadata,
   from `https://archive.ubuntu.com/ubuntu/pool/universe/s/shellcheck/shellcheck_0.9.0-1_amd64.deb`.
   Size 2,845,342 bytes; SHA-256 from the existing Ubuntu package index:
   `eadf78f4dfcb1a271f47a9be5e38d124dffe9d4fea74956fab34e8c3e322a854`.
   Extract with `dpkg-deb --extract`; do not invoke package installation or hooks.

Both downloads must match their expected hash before extraction. Node tar paths
and links must remain inside the new tool directory. Each download is bounded;
no dependency/version substitution is authorized on failure.

## Checks

Copy only the current tracked frontend source/lock files to a new independent
directory. Use Node's bundled npm to restore exactly the unchanged
`web/package-lock.json`, with `npm ci --ignore-scripts --no-audit --no-fund`.
Use a new task cache and empty user configuration, with no host credentials or
secret environment variables. Stop and report if a lifecycle script is required.
Run frontend lint, tests and production build, retaining logs and source/output
hashes. No web server, login, game or model is started.

Run ShellCheck and Bash syntax checks on the normative root entry points and
the changed provider shell entry, without new suppressions. Read failures before
changing code. Frozen task scripts must remain unchanged; a failure in one is
reported as a separate blocker, not silently exempted.

Nix/devenv installation and remote CI execution are not proposed. The direct
Linux check commands will be compared with the checked-in CI definition and
reported as local evidence, without claiming remote CI passed.

The two already-restored parser wheels are separate: exact versions/hashes from
the existing uv.lock were extracted to an independent check-only directory;
no existing interpreter environment or dependency lock was modified.

This is an explicit request for additional local check-tool acquisition/execution,
not a request to relax task, dependency, system or authentication boundaries.
