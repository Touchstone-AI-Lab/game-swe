# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# BetterTeams: `/team info` turns MiniMessage tags in a team description into click and hover events

## Context

`plugin/` is the BetterTeams Paper plugin (MIT) at an upstream commit. It is a
Maven multi-module repository: the plugin itself is the `BetterTeams` module
(`plugin/BetterTeams`), built with `mvn -pl BetterTeams -am package` into
`server/plugins/BetterTeams-5.0.0.jar`; the `extensions` modules are not part of
this task.

Every team carries a free-text description that its members set with
`/team description <text>` and an operator can set with
`/teama description <team> <text>`; it is stored with the team. `/team info
[team|player]` prints the team's info screen: one line per field (`Name:`,
`Description:`, `Open:`, `Score:`, `Balance:`, `Level:`, `Limits:`, `Tag:`,
`Anchor:` and the member lists), each starting with the plugin's message prefix
(`prefixFormat` in `config.yml`, `[BetterTeams] ` by default) and built from a
`messages.yml` template such as `info.description: '&6Description: &b{0}'`.
Plugin text understands legacy `&` colour codes and MiniMessage tags: formatting
tags such as `<red>`, `<#ff0000>`, `<bold>`, `<italic>` and `<reset>`, and
interactive or content tags such as `<click:...>`, `<hover:...>`,
`<insertion:...>` and `<lang:...>`.

## Symptom

Anyone who can set a description can put MiniMessage tags into it, and the info
screen interprets all of them. From the console:

```text
> teama create raid
[BetterTeams] That team has been created
> teama description raid <click:run_command:/say injected>CLICKME</click> <red>hello
> team info raid
[BetterTeams] Name: raid
[BetterTeams] Description: CLICKME hello
[BetterTeams] Open: false
...
```

The console only shows the plain text, but the `Description:` line that reaches
a viewer is a chat component in which `CLICKME` carries a click event running
`/say injected` as whoever clicks it: for an in-game viewer the word is
clickable and the command runs with that viewer's permissions. `<hover:...>`
produces tooltips, `<insertion:...>` makes shift-clicking the text type into the
viewer's chat box and `<lang:...>` replaces the typed text with game text, and in
every case the tag text itself has disappeared from the line. A description is
player-controlled input and must never be able to do this.

## Task

Repair the plugin so that the info screen never turns a team description into
anything but formatted text:

- Every tag in a description other than a colour, decoration or reset tag —
  `<click:...>`, `<hover:...>`, `<insertion:...>`, `<lang:...>` and the like —
  is shown as the literal text that was typed:
  `<click:run_command:/say injected>CLICKME</click>` appears in the
  `Description:` line exactly as written, and the component that reaches the
  viewer carries no click event, no hover event and no insertion anywhere and
  consists of text only.
- Colour and decoration formatting in a description keeps working as before:
  named and hex colour tags (`<red>`, `<#ff0000>`), decoration tags (`<bold>`,
  `<italic>`, `<underlined>`, ...), `<reset>` and legacy `&c`-style codes keep
  their effect with the tag text gone, so `<red>hello</red> <bold>team</bold>`
  still renders `hello` in red and `team` in bold, and text after `<reset>` loses
  the colour and decorations opened before it. Whether `<gradient>` and
  `<rainbow>` still apply is not evaluated.
- A description without any tag is shown exactly as typed after
  `Description: `.
- The rest of the info screen is unchanged: every line still starts with the
  plugin prefix, the `Description:` line keeps the template's formatting (the
  `&6` label and the `&b` value colour), and the other fields (`Name:`,
  `Tag:`, ...) are printed as before.

Keep the change inside `plugin/BetterTeams/src/main`. The build files
(`plugin/pom.xml`, `plugin/BetterTeams/pom.xml`, the extension `pom.xml`
files) and the existing tests under `plugin/BetterTeams/src/test` are frozen:
the verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with Apache Maven 3.9.11
(`mvn -o -pl BetterTeams -am package`), runs the upstream JUnit suite of the
`BetterTeams` module, and then loads the built jar into a real Paper 1.21.11
dedicated server without players. There it creates teams and sets their
descriptions from a console-type command sender (`/teama create`,
`/teama description`), runs `/team info <team>` as that sender and inspects the
chat components it receives: their plain text, the colours and decorations of
the text, and any click, hover, insertion or non-text components in them.
