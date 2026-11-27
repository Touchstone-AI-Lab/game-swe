# Writing live-server suites: lessons from the hand-authored Minecraft tasks

These notes summarise what the maintainers of `benchmarks/minecraft-core` learned
while writing GcbHarness suites for real Paper plugins. The `harness/` folder
next to this file holds the harness API source; `suites/` holds maintainer
suites for other repositories together with their live-server design notes.

## The server

- Paper 1.21.11 build 132, Java 21, headless, `--network=none`, no players,
  world `world` (flat), `allow-nether=false`. Loopback HTTP works.
- The grader plugin is generated with `depend: [GcbHarness, <plugin>]`, so the
  candidate plugin is loaded and enabled before any suite runs.
- The harness refuses to run any case when the candidate plugin is not enabled
  ("candidate plugin not enabled"): the whole result is then incomplete and
  nothing is graded. A starter must therefore start up; a defect that makes
  `onEnable` throw cannot be graded at start-up.
- Entities do not tick normally without a player nearby; do not rely on mob AI.
- Do not disable and re-enable the candidate plugin: Paper 1.21.11 closes the
  plugin classloader on disable, so `enablePlugin` fails for every submission.

## Observing output

- `GcbSenders.recording()` is a console sender whose `messages()` records plain
  text. It works for plugins that call `sender.sendMessage(String)`.
- Plugins that send chat through a shaded adventure-platform (`BukkitAudiences`)
  map every `ConsoleCommandSender`, the recording proxy included, to the real
  server console: the recording sender then sees nothing although the server log
  shows the message. Use Paper's
  `Bukkit.createCommandSender(component -> lines.add(PlainTextComponentSerializer.plainText().serialize(component)))`
  and dispatch with `GcbCommands.dispatch(sender, "...")`. If a case sees no
  output while the log shows it, switch to this sender.
- Console warnings: attach a `java.util.logging.Handler` to the root, server and
  plugin loggers and format with `SimpleFormatter.formatMessage` so `{0}`
  parameters are substituted.

## Timing

- Many plugins run sub-commands asynchronously. Make such a case a ticked
  `GcbScript` that `waitUntil`s the last expected line (a footer, a success or an
  internal-error line) instead of asserting right after dispatch.
- A synchronous case holds the main thread for its whole duration; use that
  deliberately when a defect is about main-thread scheduling.

## Configuration and start-up defects

- Data files can be seeded before start-up (the task's `seed` map, copied to
  `plugins/<plugin>/`). Seed only files the starter still enables with; a
  seeded file that makes `onEnable` throw leaves every run incomplete.
- To grade a start-up defect, write the offending file under
  `plugin.getDataFolder()` from the suite and trigger the plugin's own reload
  command, which usually runs the same initialisation as `onEnable`; state in
  the exam that the start-up symptom is exercised through reload.
- Order cases (`@GcbCase(order = n)`) so that targets which leave the starter
  broken run last, and restore files, worlds and entities in `finally` blocks.

## Asserting

- Derive expectations from the public exam and the plugin's own public outputs
  (commands, events, API objects, files). Read counts such as page totals at run
  time instead of hard-coding them when they depend on permissions or defaults.
- Reading a private field is acceptable only to reach the plugin's own registry
  when no public accessor exists, never to decide the outcome by itself.
