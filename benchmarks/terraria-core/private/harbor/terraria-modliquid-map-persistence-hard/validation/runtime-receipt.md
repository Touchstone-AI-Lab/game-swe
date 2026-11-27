# Runtime receipt

- Runtime providers: container (source projection) and local-files (engine inputs)
- Base image: `mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim`
- Pinned digest:
  `sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c`
- Evaluation language/runtime: .NET SDK 8.0.419 plus Python 3
- Network during evaluation: disabled
- Behavioral boundary: exhaustive source projection plus task-specific real tModLoader `2026.7.3.0` dedicated-server assertions; client-only rendering and MonoMod IL execution remain source-projection checks as disclosed in `engine-rubric.json`
- Engine source: official tModLoader archive `sha256:6f51610f4b0f167d1620d0e8c83264ba14e047421e97d9f8053eb40e3d764e1a`
- Publicizer input: Krafs.Publicizer 2.2.1 `sha256:f411bf4ff10b039fbc09e4fcd1a20615e26fa08a5475c8f995ba2477535fa283`
- Revision-3 evaluator image:
  `sha256:35a05341d87f2ecb37f2d3cd5fc53ff2b053b7600a507d8a396b7bd7a81ff97f`

Task identity is isolated by required source paths, catalog metadata, private
test mounts, and the task-specific content receipt.
