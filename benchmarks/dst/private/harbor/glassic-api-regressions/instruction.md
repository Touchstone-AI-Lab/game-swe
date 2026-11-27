# Harbor workspace

The mod to repair is the source tree in `/app/mod`; the verifier grades that directory.

# Glassic API: recipe sorting and mod skins break other mods

## Context

`/app/mod` is **Glassic API** (Apache-2.0) by Ducklantis, a library mod for
Don't Starve Together that other mods depend on. It exposes a global
`GlassicAPI` table. The table has helpers to register item atlases, add
recipes and move a recipe within the crafting menu's filters
(`GlassicAPI.RecipeSortBefore` and `GlassicAPI.RecipeSortAfter`), and a skin
handler (`GlassicAPI.SkinHandler`) that lets mods add skins, including skins
for the base game's characters. The comments above each function in
`modmain.lua` document the API. The library code is `modmain.lua` and the
files under `main/` and `utils/`.

Our dedicated server runs the library with its default settings, together
with mods that depend on it.

## Reports from mod authors

> We move our recipes into the Tools filter with `RecipeSortAfter` and
> `RecipeSortBefore`, sometimes next to a base-game recipe and sometimes to
> the end of the filter by passing no anchor recipe. Since then, players say
> base-game recipes are missing from that filter in the crafting menu. Some
> of them see only one or two recipes in it.

> Our character mod gives Wilson extra skins through
> `GlassicAPI.SkinHandler.AddModSkins`. In a game hosted from a client,
> Wilson disappears from the character selection as soon as anyone has
> spawned. The same thing happens on our dedicated server: after a player
> spawns, `wilson` is no longer in the game's `DST_CHARACTERLIST`.

> Since we added Glassic API, `AnimState:GetSkinBuild()` returns `nil`
> instead of an empty string for items that have no skin, and our code that
> matches on the build name throws. When an unskinned item is removed, an
> `onremove` handler that reads its skin build even gets a Lua error from
> Glassic API. Items with our mod skins still report the mod skin's build.

> We give some skins a `test_fn` in `AddModSkins` so that only supporters can
> use them. Every player still finds those skins in their skin inventory,
> whatever the test says. Skins without a test should be available to
> everyone, and they are.

> Our Wendy mod adds an axe skin with `exclusive_char = "wendy"`. The default
> skin selection offers it to every character, not only to Wendy.

> Spawning as a base-game character that no mod has given skins to works as
> before, and so does spawning as our mod character, which also has skins
> from `AddModSkins`.

## Expected behaviour

- `GlassicAPI.RecipeSortAfter(a, b, filter)` leaves recipe `a` directly after
  recipe `b` in that filter, and `GlassicAPI.RecipeSortBefore(a, b, filter)`
  leaves it directly before `b`. With no `b`, `a` moves to the end of the
  filter. This works wherever the two recipes are in the filter, and as the
  comments in `modmain.lua` describe.
- After any sort, the filter still lists every recipe it had, each exactly
  once. Its `recipes` table stays a proper Lua sequence (indices `1..n` with
  no gaps), which is how the crafting menu reads it.
- Adding mod skins for a base-game character never removes that character
  from `DST_CHARACTERLIST`, however many spawn requests follow. A spawn
  request for that character, repeated any number of times, still spawns
  that character.
- A spawn request for a base-game character without mod skins still spawns
  the requested character.
- A mod character that has mod skins is added to `DST_CHARACTERLIST` only
  while its spawn request is being checked, so that its skins can be
  validated. The request spawns the mod character, and afterwards the mod
  character is no longer in `DST_CHARACTERLIST`.
- `AnimState:GetSkinBuild()` returns an empty string for an entity without a
  skin, as the base game does, and never raises an error, including while
  the entity is being removed. For an entity with a mod skin it still
  returns the mod skin's build.
- The skin inventory (`TheInventory:GetFullInventory()`) lists a mod skin
  only when the skin is valid for the user, so a skin whose `test_fn`
  refuses is left out. Mod skins without a test are still listed.
- The default skin selection offers a character-exclusive mod skin only to
  the characters it is exclusive to. Other skins of the item are still
  offered to every character.

## Evaluation

The verifier runs the library on a real Don't Starve Together dedicated
server (Steam app 343050, build 24700372), offline, with the default
settings. It calls the public `GlassicAPI` functions the way a dependent mod
does. It sorts recipes of the base game's `TOOLS` crafting filter and puts
the filter back after each check. It adds mod skins for Wilson and for a mod
character (registered by name in `MODCHARACTERLIST`, as the mod loader does)
with `GlassicAPI.SkinHandler.AddModSkins`. It sends spawn requests through
the game's `ValidateSpawnPrefabRequest` for a client that owns only the
default skins. It spawns base-game items, gives one a mod skin's name as the
library does, and reads `AnimState:GetSkinBuild()`, also from an `onremove`
handler. It adds axe skins with and without a `test_fn` and with an
`exclusive_char`, reads `TheInventory:GetFullInventory()`, and asks the
default skin selection (`screens/redux/defaultskinselection`) for the axe's
skins through `GetSkinsList` on a popup opened for a character. It checks
the order and contents of the filter's `recipes` table, the character list,
the character each spawn request produces, the skin builds, and the skins
that are listed and offered.
