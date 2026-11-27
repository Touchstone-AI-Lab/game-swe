# Maintenance notes: logic-processor-regressions

## Upstream

- Repository: https://github.com/Anuken/Mindustry (GPL-3.0; the GitHub licence API
  reports `GPL-3.0` and `LICENSE` in the starter is the GPL version 3 text).
- Base: release tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`, the
  commit the pinned `server-release.jar` (SHA-256
  `e41289c32bcf765eb50fa131e6b515d741e20f7843fb567d3aa949e7461f22ab`) was released from.
- The starter is `core/src`, `server/src`, `annotations/src`, `LICENSE` and `README.md`
  of that commit (no assets, Gradle files or tests), with these upstream changes:

| Report | Upstream fix | In v159.7? | Starter | Reference |
| --- | --- | --- | --- | --- |
| failed `sensor` reads keep stale values | `7e416f4251e7cb997482e580851d260ecb220d1f` (PR #12391, first released in v160) | no | as released | fix applied |
| replaced linked block keeps its old link name | `58e21f32b4d1445fa1b8ecd7360bfac4e0a8930b` (issue #12280) | yes | fix reverted | as released |
| `format` ignored when the print buffer is full | `622c449a553ecdb0ef67485705444bf90a646536` (issue #12054) | yes | fix reverted | as released |
| world processor holding query results breaks saving | `68145c1bac5eba4f2b1c6ebe340550930dfbb6d1` (issue #11958) | yes | fix reverted | as released |

All four are real upstream defects that shipped in a release: the sensor defect is
present in v159.7 itself, the other three shipped in 157.x/158.x releases before their
fixes. No defect is injected. `solution/after` carries the three changed files of the reference
(`LExecutor.java`, `LogicBlock.java`, `TypeIO.java`).

## Defects

- `LExecutor.SenseI`: when the target is `Senseable` but the sensed value is neither a
  `Content` nor an `LAccess`, the output is not written; the upstream fix returns early
  for the handled cases and clears the output at the end.
- `LogicBlock.LogicBuild.updateTile`: when the building on a linked tile changes to a
  different block, the link keeps its cached `logicVar` and name; the fix clears both and
  recomputes the name with `findLinkName`.
- `LExecutor.FormatI`: an early return when the buffer holds `maxTextBuffer` (400)
  characters; the fix replaces the placeholder unconditionally and truncates afterwards.
- `TypeIO.writeObject`: a `Seq` value (what `@queries` holds) throws
  `IllegalArgumentException: Unknown object type`; the fix writes it as null.

## Suite design

Eleven cases on the real server (`tests/suite/.../TaskSuite.java`): one sentinel, four
targets, six preserved. Every case builds its own flat test world, places a logic
processor (or world processor) linked to a message block with the public `configure`
link toggle, loads code with `updateCode`, advances buildings tick by tick and reads the
message block's text; save cases use `SaveIO` round trips. Only processor output, block
code and world state are observed.
