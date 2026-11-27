# Local files provider

`rhenium-local-files` is an independent, optional `rhenium.auth_providers`
distribution. It snapshots explicitly selected local files without network,
Steam access, passwords, or modification of the source installation. A local
session contains no credential and does not verify ownership or confer a licence.

The source schema is `kind: local-files`, an absolute `path`, and an `include`
array of unique, non-overlapping relative file/directory paths. A `path` may use
`${VARIABLE}` placeholders, resolved from the environment when the snapshot is
taken, so a shared runtime catalog can name an operator's own directory instead of
one machine's layout. An unset or empty variable fails closed before anything is
read. No wildcard expansion is done.
The source and cache may not overlap. Symlinks and special files are rejected,
including inside selected directories and selected path ancestors. An unchanged
complete cache can be reused. A partial or changed cache fails closed and must be
inspected/pruned explicitly before retrying; acquisition never overwrites it.

Optional `expectedFiles` and `sha256` are passed through for the owning runtime
builder to enforce; this provider does not interpret them. Do not include personal
Mods, saves, account files, or caches in the selection. Restricted snapshots stay
in ignored local state and must not enter wheels, releases, or uploads.

Use the normal explicit `rhenium auth login local-files` and `rhenium runtime
prepare <runtime-key>` lifecycle with a state-local runtime catalog. Login only
creates an empty local session. Unit tests use temporary files, never real games.
