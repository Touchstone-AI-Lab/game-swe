# Maintenance notes: betterteams-help-page-bounds

## Upstream

- Repository: https://github.com/booksaw/BetterTeams (MIT, `LICENSE` kept in
  the starter; GitHub licence API and the file at the base commit agree).
- Base commit: `96e725761ea668082e9d8cd6eb3b2bf9fbe3d437` ("5.1.0", parent of
  the fix).
- Fix: merge commit `a23d42f3bad67d40fe44a766e458f1b311b3e866` of PR #994
  "Fix null prefix and improve help page input handling" (head `df911fd0`,
  merged 2026-04-26), closing issue #993 (reported on Paper 1.21.11).
- The starter is `git archive` of the base commit without `.github/`, `wiki/`
  (1.4 MB of documentation) and `BetterTeams.png`; none takes part in the
  build. The `extensions` modules stay because the root `pom.xml` lists them
  in the reactor (they are not built: `-pl BetterTeams -am`).

## Defect

`HelpCommand.getPage(request, maxPage)` parses the requested page and returns
`page - 1` after clamping only the upper bound to `maxPage` (not
`maxPage - 1`). Page `0` and negative pages therefore become a negative list
index (`permissiveCommands.get(-7)` throws `IndexOutOfBoundsException`, which
`BooksawCommand.runExecution` turns into the `internalError` message), and a
page past the end starts the loop at `COMMANDS_PER_PAGE * maxPage`, past the
list, so the footer names page `maxPage + 1` of `maxPage` with no entries.
Independently, `MessageManager.getPrefix()` returned
`getPrefixComponent().insertion()` — the Adventure component's insertion text,
which is never set — so `createClickableHelpMiniMessage` concatenated the
string `"null"` in front of every page entry.

## Reference fix

`solution/after/` carries the upstream main-source change only:
`HelpCommand.getSanitzedPage` clamps `page <= 0` to the first page and
`page > maxPage` to the last page (and handles `maxPage == 0`), the loop bounds
become `min(start + 7, size)`, and `MessageManager.getPrefix()` returns the
service's stored prefix string. The upstream PR changed no tests; the 44 base
tests (extension loader and placeholder suites) pass with and without the fix.

## Build

Maven multi-module (`betterteams-parent` with modules `BetterTeams` and
`extensions/*`), no committed Maven wrapper, `maven.compiler.source/target 21`,
`spigot-api 1.20-R0.1-SNAPSHOT`, JUnit 6.0.3 (BOM) + Mockito, JaCoCo agent
during `test`, shaded jar written by `maven-jar-plugin` to
`${maven.multiModuleProjectDirectory}/server/plugins/BetterTeams-5.1.0.jar`
(the build runs from the repository root, so the artifact is
`server/plugins/BetterTeams-5.1.0.jar` relative to the workspace). The catalog
therefore declares `wrapper: false`, `tool_version: "3.9.11"` and
`module: "BetterTeams"`; the verifier and agent images install Apache Maven
3.9.11 (SHA-512 pinned in `materialize.py`) before warming the cache with
`dependency:go-offline test` and proving `-o clean test package`. Surefire
reports live under `BetterTeams/target/surefire-reports`, which is why
`verify.py` looks below `build.module` as well as the workspace root. Frozen
paths are the root, module and extension `pom.xml` files plus
`BetterTeams/src/test` (and the never-present `.mvn`/`mvnw`, so a submission
cannot smuggle a wrapper in).

## Why the repository matters

The exam no longer names the classes involved; it shows the console output and
the broadcast. The solver must follow the page arithmetic in `HelpCommand.onCommand`
(`maxPage`, the 0-based `page`, the loop bounds) and separately trace why the
prefix is `null` through `MessageManager.getPrefix()` →
`MessageService.getPrefixComponent()` versus `getPrefix()`. `getPrefix()` has
three callers: the two help-line builders and the `/teama chest
disableclaims|enableclaims` broadcasts, which concatenate it in front of a
`Bukkit.broadcastMessage` string. A repair inside `HelpCommand` only (for example
building the help line from `getPrefixComponent()`) leaves the broadcasts
starting with `null`; a fix that only catches the exception, or only pins one page
bound, leaves a visible symptom.

## Live-server design

BetterTeams sends chat through its shaded adventure-platform-bukkit, whose
`BukkitAudiences.sender()` maps every `ConsoleCommandSender` — the harness
`GcbSenders.recording()` proxy included — to the real server console, so a
recording sender receives nothing. The suite instead uses Paper's
`Bukkit.createCommandSender(consumer)` (an operator-level console-type sender
whose feedback goes to a consumer; the harness uses the same sender for
Brigadier commands) and dispatches through `GcbCommands.dispatch`. BetterTeams
runs sub-commands off the main thread (`SubCommand.runAsync` defaults to
`true`), so every case is a ticked `GcbScript` that waits for the footer, the
single help line, or the plugin's internal-error line. Page counts are read
from the footer at run time rather than hard-coded (they depend on the sender's
permissions). Cases: one sentinel; four preserved cases (`/team help`,
`/team help 1`/`2`, `/team help <last>`, `/team help create`) that pass on the
starter; three target cases that fail on the starter (`null` prefix on every
entry, `/team help 0`/`-1` internal error, `/team help <last+1>`/`99` footer
naming a page past the end with no entries).

Additional cases (0.2.0): `a page argument that is not a number shows the first
page` (preserved: `/team help notapage` falls back to the first page, which holds
on the starter because `getPage` catches the `NumberFormatException`) and `chest
claim broadcasts carry the plugin prefix` (target). The suite registers itself as
a listener for `BroadcastMessageEvent` in `onEnable(grader)` and records the plain
text of every broadcast; the case runs `/teama chest disableclaims` then
`enableclaims` and checks that each announcement, after `&`/`§` colour codes are
removed, starts with the rendered `prefixFormat` (`[BetterTeams] `). The reference
fix returns the raw `prefixFormat` string, so the broadcast text carries the
untranslated `&` codes; the check accepts both raw and translated codes.

## Merge review (0.2.0)

Considered and left out: the commits around PR #994 are version bumps (`e9cd930` 5.1.1, `837c19e` 5.1.2), the merge `21c781c` of the same PR and `971aa50` ("Fix SQL issue", storage, a different family). The prefix defect itself has a third caller, the `/teama chest` claim broadcasts, which 0.2.0 grades as an extra target of the same fix.
