# BetterTeams: `/team help` crashes on page 0, prints phantom pages, and plugin lines start with `null`

## Context

`plugin/` is the BetterTeams Paper plugin (MIT) at an upstream commit. It is a
Maven multi-module repository: the plugin itself is the `BetterTeams` module
(`plugin/BetterTeams`), built with `mvn -pl BetterTeams -am package` into
`server/plugins/BetterTeams-5.1.0.jar`; the `extensions` modules are not part of
this task.

Every plugin message is meant to start with the configured message prefix, the
`prefixFormat` entry of `plugins/BetterTeams/config.yml`
(`&7[&6BetterTeams&7] ` by default, shown as `[BetterTeams] `). `/team help
[page|command]` is paged: seven commands per page, a header line, one line per
command (`/team <command> <arguments> - <description>`, each line starting with
the message prefix) and a footer `---- Page <n>/<last> - /team help <page> ----`,
where `<last>` depends on the commands the sender may use. `/team help <command>`
prints the single help line of that command, without a prefix.

## Symptom

From the console (or as an operator):

```text
> team help 0
[BetterTeams] ---- BetterTeams Help ----
[BetterTeams] Something went wrong while executing that command, please report it to your server owners

> team help 99
[BetterTeams] ---- BetterTeams Help ----
[BetterTeams] ---- Page 7/6 - /team help <page> ----

> team help
[BetterTeams] ---- BetterTeams Help ----
null/team delhome - Delete your team's home
null/team ally <team> - Used to request an alliance with another team
... (five more lines, each starting with null)
[BetterTeams] ---- Page 1/6 - /team help <page> ----
```

Page `0` and negative pages end in an internal error (the console also logs an
exception), a page past the last one
prints a footer naming a page that does not exist and no commands, and every
command line of a normal page starts with the text `null` instead of the prefix.
The same `null` appears in front of other plugin lines: when an administrator
runs `/teama chest disableclaims` or `/teama chest enableclaims`, the message
broadcast to the whole server reads `null` followed by the announcement. The page
numbers above are what a console sender with every permission sees; your server
may list a different number of commands.

## Task

Repair the plugin so that:

- `/team help 0` and every page number below `1` show the first page: the same
  header, command lines and `Page 1/<last>` footer as `/team help`, and no
  internal error.
- Any page number greater than the last page shows the last page: the footer
  names `Page <last>/<last>` and the lines are exactly the commands of that page.
- Each command line of a help page starts with the configured message prefix
  (rendered like the prefix of every other plugin message, so `[BetterTeams] `
  with the default configuration), never with `null`, followed by
  `/team <command> ...`.
- The chest-claim announcements broadcast by `/teama chest disableclaims` and
  `/teama chest enableclaims` start with the configured prefix
  (`[BetterTeams] ` once colour codes are removed) instead of `null`.
- Everything else keeps working unchanged: `/team help` and `/team help 1` show
  the first page, `/team help 2` the second, `/team help <last>` the final page
  with its remaining commands, an argument that is neither a number nor a
  command name (for example `/team help notapage`) shows the first page, and
  `/team help create` still prints exactly the single help line of the `create`
  command.

Keep the change inside `plugin/BetterTeams/src/main`. The build files
(`plugin/pom.xml`, `plugin/BetterTeams/pom.xml`, the extension `pom.xml`
files) and the existing tests under `plugin/BetterTeams/src/test` are frozen:
the verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with Apache Maven 3.9.11
(`mvn -o -pl BetterTeams -am package`), runs the upstream JUnit suite of the
`BetterTeams` module, and then loads the built jar into a real Paper 1.21.11
dedicated server without players. There it runs `/team help` with no page, with
valid pages, with `0`, negative, too-large and non-numeric pages and with a
command name, and `/teama chest disableclaims` and `/teama chest enableclaims`,
from a console-type command sender; it checks the header, command lines and
footer the sender receives and the text of every server broadcast
(`BroadcastMessageEvent`).
