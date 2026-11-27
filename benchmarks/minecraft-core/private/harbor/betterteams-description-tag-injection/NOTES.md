# Maintenance notes: betterteams-description-tag-injection

## Upstream

- Repository: https://github.com/booksaw/BetterTeams (MIT, `LICENSE` kept in
  the starter; the GitHub licence API and the file at the base commit agree).
- Base commit: `b35644ce54688d87dd3a1435cefedfe7720d3707` ("Add apollo
  teamview (#980)", version 5.0.0, parent of the fix).
- Fix: merge commit `382d34a6162d860504fa2bed1040b0f0ac1d24b4` of PR #986
  "Fix teamInfo formatting" (head `d1dba3c6`, merged 2026-04-14). The
  follow-up CHANGELOG entry reads "Fixed minimessages injection exploit -
  Credit RVSkeLe".
- The starter is `git archive` of the base commit without `.github/`, `wiki/`
  (documentation) and `BetterTeams.png`; none takes part in the build. The
  `extensions` modules stay because the root `pom.xml` lists them in the
  reactor (they are not built: `-pl BetterTeams -am`).

## Defect

`InfoCommand.getInfoMessages` substitutes the stored, player-controlled team
description into the `info.description` template (`&6Description: &b{0}`) and
`displayTeamInfo` sends every line through `MessageManager.sendFullMessage`,
which is `MessageService.sendFullMessage` → `Formatter.absolute().process`:
a MiniMessage instance built with `TagResolver.standard()`, so `<click:...>`,
`<hover:...>`, `<insertion:...>` and every other standard tag inside the
description are parsed. A description such as
`<click:run_command:/say injected>CLICKME</click>` becomes a component whose
`CLICKME` carries a `run_command` click event, executed as whoever clicks it
(`/team info` is available to every player), and the tag text disappears.

## Reference fix

`solution/after/` carries the upstream main-source change only:
`Formatter.safe()` (a MiniMessage instance whose tag set is
`StandardTags.color()`, `decorations()` and `reset()` plus the legacy `&`
pre-processor), `MessageService.sendSafeMessage` / `MessageManager.sendSafeMessage`
(same prefix handling as `sendFullMessage`), and `InfoCommand.displayTeamInfo`
switching to `sendSafeMessage`. Upstream changed no tests; the 44 base tests
(extension loader and placeholder suites) pass with and without the fix.

## Build

Maven multi-module (`betterteams-parent` with modules `BetterTeams` and
`extensions/*`), no committed Maven wrapper, `maven.compiler.source/target 21`,
`spigot-api 1.20-R0.1-SNAPSHOT`, shaded `adventure-text-minimessage` 4.26.1
and `adventure-platform-bukkit` 4.4.1 relocated to
`com.booksaw.betterTeams.lib.net.kyori`, JUnit 6.0.3 (BOM) + Mockito, JaCoCo
agent during `test`, jar written by `maven-jar-plugin` to
`${maven.multiModuleProjectDirectory}/server/plugins/BetterTeams-5.0.0.jar`
(the build runs from the repository root, so the artifact is
`server/plugins/BetterTeams-5.0.0.jar` relative to the workspace). The catalog
declares `wrapper: false`, `tool_version: "3.9.11"` and `module: "BetterTeams"`
exactly like `betterteams-help-page-bounds`; the verifier and agent images
install Apache Maven 3.9.11 (SHA-512 pinned in `materialize.py`) before warming
the cache with `dependency:go-offline test` and proving `-o clean test package`.
Surefire reports live under `BetterTeams/target/surefire-reports`, below
`build.module`. Frozen paths are the root, module and extension `pom.xml` files
plus `BetterTeams/src/test` (and the never-present `.mvn`/`mvnw`, so a
submission cannot smuggle a wrapper in).

## Why the repository matters

The solver must trace the description from `Team.getDescription()` through the
`info.description` template, `MessageManager.sendFullMessage`,
`MessageService.sendFullMessage` and `Formatter.absolute()` to find where the
untrusted text meets the full MiniMessage tag set, and then choose a boundary
at which to restrict it without losing the colour and decoration formatting
the same pipeline relies on (the template's `&6`/`&b` codes, colour tags in
descriptions). Escaping every tag (`MiniMessage.escapeTags`) or switching the
line to a plain-text send breaks colour tags in descriptions; neutralising
only `<click` leaves hover and the other event tags parsed.

## Live-server design

BetterTeams sends chat through its shaded adventure-platform-bukkit 4.4.1
(relocated to `com.booksaw.betterTeams.lib.net.kyori`). Two consequences for a
player-free grader:

- `BukkitAudiences.sender()` maps every `ConsoleCommandSender` — the harness
  `GcbSenders.recording()` proxy included — to the real server console, so a
  recording sender receives nothing.
- For every other non-player `CommandSender` the platform's Spigot chat facet
  (`sender.spigot().sendMessage(BaseComponent[])`, which would keep click and
  hover events) is disabled: `SpigotFacet.SUPPORTED` requires
  `BungeeComponentSerializer.isNative()`, which is false for the relocated
  serializer. The platform falls back to `BukkitFacet.Chat`, i.e.
  `sender.sendMessage(String)` with legacy `§` codes, so colours and decorations
  arrive but click/hover events do not (they only reach real players through
  the packet facet). This was verified on the server with a `java.lang.reflect.Proxy`
  sender that recorded `spigot()` arrays: the plugin never called it.

The suite therefore uses Paper's `Bukkit.createCommandSender(consumer)`, an
operator-level sender whose feedback arrives as native `Component`s (Paper
deserialises the legacy text), dispatched through `GcbCommands.dispatch`. The
discriminating assertion of the two target cases is the literal tag text:
on the starter the tag is parsed and its text is consumed (`Description:
CLICKME hello`), after a valid fix the typed tag appears verbatim. The
click/hover-event walk over the component tree is kept as a guard for any
component-preserving path but cannot fail on the legacy path; a fix that strips
the tag text instead of showing it fails the literal-text assertion by design
(the exam requires the text as typed). Effective colours and decorations are
computed by walking the component tree with inheritance, so the assertions do
not depend on how the formatter nests or compacts the components.

Sub-commands run off the main thread (`SubCommand.runAsync` defaults to
`true`), so every case is a ticked `GcbScript` that waits for the plugin's reply
(`/teama create` → "That team has been created", `/teama description` →
"That teams name has been changed" [sic, the upstream success message],
`/team info` → the `Tag:` line, which is the last field printed for a team
without members; the anchor line may follow within the extra wait ticks).
Teams are created per case with distinct names through the admin commands
(`/teama description` joins the arguments with single spaces and leaves a
trailing space, which the assertions strip).

Cases: one sentinel; three preserved cases that pass on the starter (a plain
description is shown as typed; every line keeps the prefix, the `&6` label and
`&b` value colours and the `Name:`/`Tag:` fields; `<red>`, `<bold>` and `&a` in
a description keep their effect); two target cases that fail on the starter
(the `<click:run_command:...>` tag is printed literally and attaches no click
event; the `<hover:show_text:...>` tag is printed literally and attaches no
hover event).

## 0.2.0 changes

The exam no longer names `InfoCommand`, `MessageManager`, `MessageService` or
`Formatter`, and no longer says where the tag set is chosen; it shows the info
screen and states the formatting contract. The solver has to trace the
description from the info screen through the message pipeline to the MiniMessage
instance and restrict it at a boundary that keeps colour, decoration and reset
formatting.

New cases:

- `decoration tags and reset still format a description` (preserved):
  `<italic>slanted</italic> <gold><underlined>gilded</underlined> <reset>plain &lstrong`
  renders `slanted gilded plain strong` with italic, gold + underlined, nothing
  of that after `<reset>`, and bold from `&l`. Holds on the starter (full tag
  set). A repair that keeps only colour tags, or drops `<reset>`, fails it.
- `an insertion tag in a description is shown as text` (target):
  `<insertion:/team join gcb>INSERTME</insertion>` is printed literally and no
  node carries an insertion.
- `a translatable tag in a description is shown as text` (target):
  `rock <lang:block.minecraft.stone> end` is printed exactly as typed and the
  line consists of text components only.

The two new targets stop a deny-list repair that neutralises only `<click` and
`<hover` (the target-negative).

Rejected merge: the adjacent upstream commit `df8385d` ("Fix description
command", 2026-04-14, two commits after the fix) closes the same injection on
`/team description` without arguments, which shows the sender's own team
description. That sub-command is a `TeamSubCommand`: it needs a `Player` who is
a member of a team, so its symptom cannot be reproduced on a player-free server
and a target case would depend on a `GcbProxies.player` stand-in, which the
authoring requirements forbid. The task therefore keeps the single upstream fix
(PR #986).
