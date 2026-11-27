# Maintenance notes

- Paper 1.21.11 build 132 (Java 21) is the pinned server. The 1.21 line is the
  last one supported by the broadest set of plugin repositories; the 26.x line
  requires Java 25 and had little plugin coverage when this pack was authored.
- The base image is built once per operator with network access (paperclip
  downloads the Mojang server jar and the dependency cache is warmed). Every
  evaluation container runs with `--network=none`.
- All task text is English. Task ids are `<repo-slug>-<short-symptom>`.
- The EULA is accepted by the operator, never by Rhenium: the operator writes
  `eula=true` to the pack's acceptance record in local Hub state
  (`packs/minecraft/<pack>/eula.txt`), which the runtime builder only reads.
- Same-JVM trust boundary: the candidate plugin runs in the same server process
  as the harness. A nonce, the exactly-one-envelope rule, `depend:` load order
  and the frozen case-name set defeat naive forgery; this is the honest-mode
  boundary documented in `docs/games/minecraft.md`.
