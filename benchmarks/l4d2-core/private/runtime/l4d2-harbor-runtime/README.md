# L4D2 Harbor verifier runtime

This is shared verifier infrastructure, not a benchmark task. It installs the
anonymous Left 4 Dead 2 dedicated-server app (`222860`), MetaMod:Source and
SourceMod from their official distribution sites. No game binaries are stored in
Git.

Build the frozen local image before running the SourceMod tasks:

```bash
rhenium auth login container
rhenium runtime prepare left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246
```

The build intentionally fails if Steam no longer returns L4D2 server build
`23990100` or if any pinned toolchain archive changes. The frozen depot manifests
and archive hashes are recorded in the task validation metadata.
