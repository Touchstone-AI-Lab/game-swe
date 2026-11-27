# Maintenance notes

- Mindustry v159.7 is the pinned server. It is the release the only actively maintained
  v8 server plugins in the candidate survey targeted when the pack was authored, and it
  was already the operator-provided jar of the previous catalog, so the runtime source
  and its digest did not change.
- Task sources: plugin and mod repositories were surveyed first (ZetaMap/MoreCommands,
  xpdustry/distributor, XCore-mindustry/XCore-plugin, Agzam4/Mindustry-plugin and
  others). They were not used: their bug fixes are mixed into large refactoring commits,
  they depend on MongoDB, Redis, Telegram or network services, or they target other game
  versions. The game's own sources have a dense history of small, well-described fixes
  with server-observable symptoms, so every task repairs Mindustry itself.
- Why a javac build instead of Gradle: the upstream Gradle build regenerates
  `mindustry.gen` with annotation processors that need the full asset tree (sounds,
  sprites, fonts, about 60 MB). Compiling the ordinary sources against the release jar,
  which already contains the generated classes and assets, reproduces the released
  server exactly while keeping the vendored tree at about 8.6 MB. The consequence is that
  fixes inside entity component templates (`entities/comp`) or assets cannot be tasks.
- The five starters are the same v159.7 tree except for the repaired files; Git stores
  the identical files once.
- All task text is English, except the required `zh` fields of the catalog.
- Same-JVM trust boundary: the candidate is the game itself. The nonce, the
  exactly-one-line rule, the frozen case names and the watchdog defeat naive forgery;
  this is the honest-mode boundary documented in `docs/games/mindustry.md`.
