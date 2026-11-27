# Rhenium Don't Starve Together repair exams

Each Markdown file in `exams/` is one self-contained repair task over a real
open-source Don't Starve Together mod. File names are for maintainers; a copy
placed in an isolated attempt directory is always named `EXAM.md`, so the model
never sees the internal task id or an ordinal.

| Exam | Upstream mod | Domains | Suggested time |
| --- | --- | --- | ---: |
| [DST Fixed: gifts and bundles misbehave when they are opened from an inventory](dst-fixed-bundle-regressions.md) | DST Fixed | inventory, events, RPC, persistence | 150 min |
| [DST Fixed: six optional modules misbehave on our server](dst-fixed-module-regressions.md) | DST Fixed | items, creatures, loot, persistence | 180 min |
| [Composting Together: the compost pile misbehaves on a dedicated server](composting-together-regressions.md) | Composting Together | containers, timers, persistence | 150 min |
| [DsMMO: skill handlers, saves and commands misbehave on a live server](dsmmo-release-regressions.md) | DsMMO | events, combat, persistence | 120 min |
| [Glassic API: recipe sorting and mod skins break other mods](glassic-api-regressions.md) | Glassic API | crafting, skins | 120 min |

## Common rules

1. The mod to repair is the source tree in `/app/mod` of the workspace (`mod/`
   in an attempt directory). Keep its layout and required files.
2. Each exam gives operator, player or mod-author reports and the expected
   behaviour. It never states how many defects there are or where they are.
3. Fix the causes, and keep every behaviour the exam says already works.
4. A complete result requires the submission-shape check and every hidden
   assertion on the pinned headless dedicated server (Steam app 343050, build
   24700372), run offline with the settings the exam states.
