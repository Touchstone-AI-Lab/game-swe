# Content Patcher: bug reports against this release

You are working on **Content Patcher**, the SMAPI framework mod that lets Stardew
Valley content packs edit game assets declaratively. The mod's source is at
`/app/StardewMods` (the mod project is `ContentPatcher/`; `Common/` is shared code
used by the same author's mods). The author guide is in `ContentPatcher/docs/`.

## Problem

Content pack authors filed the reports below against this release. They are
observations from people using the mod on a Linux server, not diagnoses, and they
do not necessarily map one-to-one onto causes in the code.

> **Path positions.** The `PathPart` token returns the wrong thing whenever I ask
> for a numeric position. `{{PathPart: assets/portraits/Abigail.png, 0}}` gives me
> `assets/portraits` instead of `assets`, position `1` gives `Abigail.png` instead
> of `portraits`, and a negative position like `-1` makes Content Patcher ignore
> the whole patch with an "invalid path fragment" error. The named parts
> (`FileName`, `DirectoryPath`, `FileNameWithoutExtension`) are fine. The author
> guide's `PathPart` tables show what numeric positions are supposed to return.

> **Tokens in nested keys.** I use `EditData` to add entries to a data asset that
> a C# framework mod exposes. One field of the entry is a dictionary, and I build
> some of its keys from my pack's dynamic tokens, like
> `"Extra": { "{{Prefix}}_speed": "{{Speed}}", "base_speed": "{{Speed}}" }`.
> The key comes out correctly (`fast_speed`), but its value is the literal text
> `{{Speed}}` instead of the token's value. The `base_speed` key, which has no
> token in it, gets the right value.

> **Positions in data models.** When I add an entry whose model has a position
> field and I write the position the way the author guide writes positions
> elsewhere, `"Offset": { "X": 15, "Y": 20 }`, Content Patcher skips the entry
> with "failed converting entry to the expected type ... requires a JSON string
> value". Setting the same field through `Fields` fails as well. Writing it as the
> text `"15, 20"` works on this server. SMAPI itself reads both forms in JSON files,
> and both should work here too.

> **Lists in new entries.** Same framework mod: its entry model starts with a
> `Tags` list containing `default`. When my pack adds a new entry with
> `"Tags": [ "alpha", "beta" ]`, the entry in the game has
> `[ "default", "alpha", "beta" ]`. An entry I write should contain exactly the
> list I wrote.

> **Text operations on things that don't exist.** A `RemoveDelimited` text
> operation whose target entry doesn't exist yet should do nothing, since there's
> nothing to remove from. Instead the data asset gains a new entry with that key
> and no value. With `EditMap`, the same operation on a map property the map
> doesn't have adds a property with no value, and the game then throws a
> null-reference error when a location reads that map's properties. `Append` on a
> missing target should keep creating it, as the author guide describes.

## Task

Diagnose and fix everything reported above. Behavior that already works must not
change: named `PathPart` fragments, nested keys without tokens, positions written
as `"X, Y"` text, text operations on entries and map properties that exist, and
appends that create a missing entry or map property.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build ContentPatcher/ContentPatcher.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless
  with a small content pack installed, and inspects the patched assets.
