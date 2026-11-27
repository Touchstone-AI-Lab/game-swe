# Harbor workspace

Complete this task in `/app/mindustry`; the verifier compiles its Java sources against the pinned Mindustry v159.7 dedicated server.

# Mindustry v159.7: logic processors misbehave on our dedicated server

## Context

`mindustry/` is the source tree of Mindustry (<https://github.com/Anuken/Mindustry>,
GPL-3.0, see `mindustry/LICENSE`) exactly as our dedicated servers run it: release
**v159.7** with the game core in `core/src`, the dedicated-server launcher and console
in `server/src`, and the annotation definitions in `annotations/src`. Game assets,
the Gradle build scripts and the upstream test suite are not part of the tree.

Our server build compiles every Java file under `core/src` and `server/src`, plus
`annotations/src/main/java/mindustry/annotations/Annotations.java`, with
`javac --release 17` against the official v159.7 `server-release.jar`, and runs the
dedicated server with the compiled classes ahead of that jar. Code generated at build
time (the `mindustry.gen` package, including the entity classes generated from the
component templates in `core/src/mindustry/entities/comp`) and every asset (maps,
bundles, sprites) come from the official jar and are not regenerated, so changes have
to be made in ordinary sources. Keep your changes inside `mindustry/core/src` and
`mindustry/server/src`.

## Reports

Players report the following problems with logic processors. Each one reproduces on a
fresh world with a logic processor linked to a message block; the snippets below are
processor code.

- **Failed `sensor` reads keep stale values.** When the sensed value is something the
  target cannot report, the output variable is left untouched:

  ```text
  set a 1
  sensor a @this null
  set b 2
  sensor b conveyor1 "copper"
  print a
  print " "
  print b
  printflush message1
  ```

  prints `1 2`. Other failed logic operations set their result to `null`.

- **Replacing a linked block keeps the old link name.** A processor linked to a conveyor
  and a message block runs

  ```text
  print junction1
  print " "
  print conveyor1
  print " "
  print @links
  printflush message1
  ```

  and shows `null conveyor 2`. After a player builds a junction over that conveyor (the
  link stays on the same tile), the message becomes `null junction 2`: the processor
  keeps calling the junction `conveyor1` and `junction1` stays `null`, so code written
  for the new block never sees it.

- **`format` stops working once the print buffer is full.** After `print "{0}"`
  followed by prints of another 397 characters, `format "ok"` leaves `{0}` in the
  message instead of `ok`. `format` can also grow the buffer past its 400-character
  limit when the buffer is almost full.

- **Some worlds can no longer be saved.** A world processor that keeps the result of a
  `query` instruction in a variable, for example

  ```text
  query circle unit @sharded 10 10 5 5
  set held @queries
  ```

  makes every save of the world fail (autosaves and the `save` console command log
  `IllegalArgumentException: Unknown object type: class arc.struct.Seq`).

## Expected behaviour

- `sensor` sets its output variable to `null` whenever the sensed value is neither a
  content nor a logic property the target supports (for example `null` or a string); the
  example above prints `null null`. Supported reads keep working: `@x` of a linked
  conveyor gives its tile x, `@type` its block, `@copper` its copper count, and sensing
  a target that is not a building (such as a number) still gives `null`.
- When a linked block is replaced by a block of a different type on the same tile, the
  link is renamed exactly as if the new block had just been linked (a junction becomes
  `junction1` when no other link is called that), the new name refers to the new block,
  and the old name no longer refers to anything. The example above then prints
  `junction null 2`. Links whose block did not change keep their names, and newly
  linked blocks are still named after their block type (`conveyor1`, `sorter1`,
  `message1`), with `@links` counting every link once.
- `format` always replaces the lowest-numbered placeholder `{0}`...`{9}` in the print
  buffer, even when the buffer already holds its maximum of 400 characters, and the
  buffer is cut back to 400 characters afterwards: the example above shows a 399-character
  message that starts with `ok`. Placeholders are still filled in order
  (`print "{1} and {0}"`, `format 5`, `format "x"` shows `x and 5`), and printing more
  than 400 characters still keeps only the first 400.
- A world whose world processors hold query results saves and loads normally, and the
  processor comes back with its code. Processor code and ordinary variables (numbers and
  strings) still survive saving and loading, so a counter kept in a variable continues
  from its saved value.

## Evaluation

The verifier compiles your tree offline as described above and starts a real headless
v159.7 dedicated server with it, without network access. A trusted plugin inside that
server builds small test worlds, runs logic processors and world processors linked to
message blocks, replaces linked blocks and saves and reloads worlds, and checks what the
message blocks show and what survives the reload.
