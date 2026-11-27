# Source and acceptance boundary

Exact single-parent target 4941919bf33fb84ff280fa64c500c4439118b5e0, base 8d978d53095287c85da0bda09b73045ff68d244f, from Cruesoe/ResearchOrganized.
Both trees have identical MIT license bytes and explicit 1.6 + Harmony metadata.
All thirteen complete production C# files are byte-exact. Both full archives were
inventoried for notices; selected source has only the author's assembly copyright
and no additional license declaration or copied-game notice. Existing code uses
native game APIs and reflection; no game implementation is packaged or stubbed.
Original local build configuration is replaced by fixed SDK 8.0.422, C#12, net472,
Krafs.Rimworld.Ref 1.6.4871, Harmony 2.4.2 and the existing locked reference packages.
The original two unchanged XML definition files are fixed task-owned runtime inputs.
Binaries, textures, upstream tests, IDE state and proprietary files are excluded.

The selected seam is the tab/visibility/window consistency fix, unrelated to any
existing RimWorld task. Private helpers are not required interfaces. Fixtures call
the public organizer and refresh methods with native ResearchManager, DefMap,
ResearchTabDef and the actual persistent MainTabWindow_Research. All changes are
bounded to fresh controlled processes and restored independently of candidate code.
A cleanup/setup failure is incomplete; candidate exceptions or incorrect native
observable state are behavioral failures. The external supervisor owns verdicts.

A later upstream thread-loading fix is deliberately excluded: the public task
invokes the seam on the game thread and does not claim background game-load support.

Authoring revision 2 (draft catalog 0.2.0) added closed/open native view-width
observations and open-window relayout/explicit-refresh observations. A real project
is moved to expand the native width through the game setter; the candidate then
re-layouts, and its cached rightViewWidth is compared with an independent native
setter recomputation. No width formula or candidate refresh helper is used as the
oracle. Native WindowStack.Add runs PreOpen/PostOpen, cleanup closes through
TryRemove, and checkpoint restoration audits original stack membership and fields.

Authoring revision 3 (catalog 0.4.0) registers the task and repairs two fixture
defects found in the first real-game runs: observation now waits for the entry
WindowStack, and the width fixture runs the game's
`ResearchProjectDef.GenerateNonOverlappingCoordinates()` after moving a project.
No case, expected value, gate, weight, exam, starter or reference changed. On
2026-10-29 the reference passed 22/22 three times, base and an independent no-op
failed the same 14 target cases, and all five declared negatives detected their
defects in the pinned real game; `controls.json` records the runs.
