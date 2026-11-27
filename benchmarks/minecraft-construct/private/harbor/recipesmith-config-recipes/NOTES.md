# Maintenance notes: recipesmith-config-recipes

## Task

Construct task: the model writes the whole Recipesmith plugin: shaped, shapeless, smelting,
smoking, blasting, campfire and stonecutting recipes from `recipes.yml` with material lists,
item tags, result names and lore, validation with the first reason in a fixed order,
registration under `recipesmith:<id>`, disabling and restoring vanilla recipes across reloads,
and the `/recipes` commands.

## Skeleton

Frozen `pom.xml`, minimal `plugin.yml`, empty `RecipesmithPlugin`. The empty skeleton builds and
enables; the `nop` control is complete and fails every case but the sentinel.

## Reference

`solution/after/` (about 520 lines of Java): `RecipeParser` (validation order, ingredients,
results), `RecipeBook` (registration, vanilla removal and restoration, file edits),
`RecipesCommand`, `RecipeException` and `RecipesmithPlugin`, plus the default `recipes.yml`.

## Live-server design

- 18 cases in `tests/suite/RecipesmithSuite.java`, sentinel first (pack 1.3.0).
- Crafting is checked through the server: `Bukkit.getCraftingRecipe` (the matched key) and
  `Bukkit.craftItemResult` (the result item) on 3 x 3 grids in `world`; cooking and
  stonecutting recipes through their Bukkit recipe objects.
- `a smelting recipe cooks in a real furnace` places a furnace at (300, -59, 300) with two
  gravel and one coal and expects four flint after 130 ticks.
- Every recipe combination was chosen so that no vanilla recipe matches the same grid.

## Pitfalls found while authoring

- `max-world-size` is 1024: a furnace outside the world border never ticks (fuel unused,
  cook time 0). The furnace sits well inside the border.
- `Material.CHAIN` does not exist in 1.21.11 (it is `IRON_CHAIN`); the blasting case uses iron
  bars and iron trapdoors.

## Fairness review

- The exam states every recipe key, the defaults, the validation order and reason texts, the
  registration key and types, the vanilla rules and the reply formats.
- Result names and lore are compared as plain text, so MiniMessage styling and the default
  italic of display names do not matter.
