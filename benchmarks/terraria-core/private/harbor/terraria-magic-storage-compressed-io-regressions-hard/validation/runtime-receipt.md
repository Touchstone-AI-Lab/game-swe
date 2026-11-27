# Local validation runtime receipt

- Runtime providers: container (source projection) and local-files (engine inputs)
- Control image tag: `gcb-terraria-msio-base:latest`
- Control image ID: `sha256:1343c6898c01da93b4d5eaaba8a92d920d6b9c011821579459f2ebc107163d0e`
- Dockerfile base image: `mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim`
- Base image digest: `sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c`
- Validation date: `2026-09-24`
- Prepared plugin evaluator image ID:
  `sha256:1afb98d967b5503b0f8eb22d9771bcee6bb2cd802d8097181cf76018d7a4f828`
- Prepared runtime artifact identity:
  `sha256:fbd3f0e8b13a4bb5a91991529c065aea8df26485ef45252e7d4a3979e7906b5d`
- Behavioral boundary: exhaustive source projection plus task-specific real
  tModLoader `2026.7.3.0` dedicated-server assertions; see
  `engine-rubric.json` for disclosed exclusions
- Engine source: official tModLoader archive
  `sha256:6f51610f4b0f167d1620d0e8c83264ba14e047421e97d9f8053eb40e3d764e1a`
- Publicizer input: Krafs.Publicizer 2.2.1
  `sha256:f411bf4ff10b039fbc09e4fcd1a20615e26fa08a5475c8f995ba2477535fa283`

The control image ID identifies the locally built task environment used for the
recorded runs. The base digest is the portable content pin used by the committed
Dockerfile. Neither hash is a claim about task quality; the control table records
the behavioral evidence.
