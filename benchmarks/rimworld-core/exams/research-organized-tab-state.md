# Keep research-tab state consistent after re-layout

Research: Organized can hide, restore and re-sort research tabs when the player
changes combination settings. In an active game, changing those settings can
shift per-tab visibility flags onto the wrong tabs or make the research window
throw when a tab is restored. A closed research window can also remember a tab
that is no longer available when it is reopened.

Repair the supplied production code under `ResearchOrganized/Source`.

- `ResearchOrganizedMain.OrganizeTabsAndLayout()` must preserve each currently
  known tab's edited information-visibility flag by tab identity when indices
  change. Rebuild the native indexed flag storage for the resulting active tabs.
  Restored or newly introduced tabs absent from the previous active set receive
  their `visibleByDefault` value. A game created while tabs are combined must be
  able to return to separate tabs without an invalid native visibility lookup.
- Repeated re-layouts must retain edits. Calls without a current game, or before
  the native visibility map is initialized, must remain safe and keep normal
  lazy/default visibility behavior.
- After every re-layout, refresh the game's persistent research window even when
  it is closed. Its tab records must match the current tab database. Retain a
  valid current tab and selected project. If the remembered tab was hidden,
  select the selected project's current tab when available, otherwise a current
  available tab. Recompute the view for that tab without reopening the window.
- `RefreshOpenResearchWindow()` must also refresh a closed persistent instance.
  Preserve unrelated layout, routing, settings persistence, colors and game behavior.

Keep the existing public API and supplied project structure. Private helpers and
storage strategies may change; no particular new method or cache field is
required. The starter has all thirteen complete upstream C# units. Its two XML
definition files are fixed operator-owned runtime inputs, outside the submission.

The target is Core-only RimWorld 1.6.4871, Harmony 2.4.2, net472 and C#12 with SDK
8.0.422. Calls in this task occur on the game thread. DLC, other Mods, screenshots,
disk saves and background-thread game loading are outside the scored scope.
Use the fixed references. Do not add dependencies, assemblies, art, game files,
credentials or generated output. Submit only the `ResearchOrganized` tree.
