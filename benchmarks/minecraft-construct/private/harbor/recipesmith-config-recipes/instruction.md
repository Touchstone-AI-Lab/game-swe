# Harbor workspace

Write this plugin in `/app/plugin`; the skeleton's `pom.xml` and anything under `src/test` are frozen and restored by the verifier.

# Write a plugin: Recipesmith, custom recipes from a configuration file

You are writing a **new** Paper plugin. The skeleton at `/app/plugin` holds:

- `pom.xml`: the frozen Maven build. It compiles `src/main/java` with Java 21 against the
  Paper API 1.21.11 (the exact API of the server that grades you, Adventure and MiniMessage
  included) and packages `src/main/resources` into `target/Recipesmith.jar`. No other library
  is available.
- `src/main/resources/plugin.yml`: plugin name `Recipesmith`, the main class and
  `api-version: '1.21'`. Add the command and the permission described below.
- `src/main/java/com/example/recipesmith/RecipesmithPlugin.java`: an empty main class.

Keep the plugin name and the main class `com.example.recipesmith.RecipesmithPlugin`. Everything
else is yours to write: add classes under `src/main/java` and resources under
`src/main/resources`.

## How the plugin is built and graded

- The verifier restores `pom.xml` (and removes anything under `src/test`), then builds offline
  with `mvn -o -DskipTests package`. You can run the same build yourself where Maven and its
  cache are available.
- The jar is loaded into a real Paper 1.21.11 dedicated server with no players and no network,
  and with an empty data folder `plugins/Recipesmith/`. Private cases then run one after
  another in that single server session. If the plugin fails to enable, no case can be graded.
- The grader runs commands on the main server thread by looking the command up in the server's
  command map and calling `Command#execute`, with its own senders:
  - a console-like sender that has every permission;
  - senders that hold only the permissions a case grants them (they are not players).

  Declare the command in `plugin.yml` and handle it with a Bukkit `CommandExecutor` (not the
  Brigadier lifecycle API). Do not give the command a `permission:` key: the plugin checks
  the permission itself and answers with the message below.
- The grader inspects the server's recipes with `Bukkit.getRecipe`, `Bukkit.recipeIterator`,
  `Bukkit.getCraftingRecipe` and `Bukkit.craftItemResult` on 3 × 3 crafting grids in the world
  `world`, and it smelts items in a real furnace block.
- Replies are compared line by line. The grader turns every message a sender gets into plain
  text (colour and formatting are dropped; a message with line breaks counts as several lines),
  trims each line and compares the sequence exactly with the lines this document specifies.
  Send nothing else to the sender.
- Every file change is written to disk before the command that caused it returns.

## The recipe file

1. **Default file.** Recipes live in `plugins/Recipesmith/recipes.yml`. When the file does not
   exist at enable, write it with exactly these values (comments and key order are free), then
   load it:

   ```yaml
   recipes:
     compact_dirt:
       type: shaped
       shape:
         - "DD"
         - "DD"
       ingredients:
         D: DIRT
       result:
         material: COARSE_DIRT
         amount: 4
   disabled-vanilla: []
   ```

2. **Recipe entries.** Every key under `recipes` is a recipe id. Its keys:

   | Key | Used by | Meaning |
   | --- | --- | --- |
   | `type` | all | `shaped`, `shapeless`, `smelting`, `smoking`, `blasting`, `campfire` or `stonecutting` |
   | `result.material` | all | the result item (a `Material` name, case-insensitive; it must be an item) |
   | `result.amount` | all | 1 to 64, default 1 |
   | `result.name` | all | optional MiniMessage text, set as the result item's display name |
   | `result.lore` | all | optional list of MiniMessage lines, set as the result item's lore |
   | `group` | all | optional recipe book group (`Recipe#setGroup` where the recipe type has it) |
   | `permission` | `shaped`, `shapeless` | optional non-empty permission required to craft the recipe |
   | `shape` | `shaped` | 1 to 3 rows of 1 to 3 characters, all rows the same length; a space is an empty slot |
   | `ingredients` | `shaped` | a map from a shape character to an ingredient |
   | `ingredients` | `shapeless` | a list of 1 to 9 ingredients, each one item of the grid |
   | `input` | cooking types, `stonecutting` | one ingredient |
   | `experience` | cooking types | a number of at least 0, default 0 |
   | `cooking-time` | cooking types | whole ticks, at least 1; default 200 for `smelting`, 100 for `smoking` and `blasting`, 600 for `campfire` |

   An **ingredient** is a material name (`OAK_LOG`), a list of material names (any one of them
   fits), or an item tag written `#namespace:key` (`#minecraft:planks`: any item of the tag
   fits). Material names are case-insensitive and must be items.
3. **Registration.** Each valid recipe is registered with the server under the key
   `recipesmith:<id>` (`new NamespacedKey(plugin, id)`) as the matching Bukkit recipe type
   (`ShapedRecipe`, `ShapelessRecipe`, `FurnaceRecipe`, `SmokingRecipe`, `BlastingRecipe`,
   `CampfireRecipe`, `StonecuttingRecipe`), with a `RecipeChoice.MaterialChoice` for every
   ingredient.
4. **Validation.** A recipe that fails a check is skipped (not registered) with the first
   failing reason, checked in this order; the other recipes still load:

   | Check | Reason |
   | --- | --- |
   | the id matches `^[a-z0-9_]{1,32}$` | `invalid id` |
   | `type` is one of the seven types | `unknown type <type>` (`none` when missing) |
   | a non-empty `permission` is used only with `shaped` or `shapeless` | `permission requires a crafting recipe` |
   | `result.material` is an item material | `unknown result material <value>` (`none` when missing) |
   | `result.amount` is 1 to 64 | `amount must be between 1 and 64` |
   | shaped: the shape is valid | `invalid shape` |
   | shaped: every character of the shape (first appearance in reading order) has an ingredient | `no ingredient for <character>` |
   | shaped: every ingredient key appears in the shape (map order) | `unused ingredient <key>` |
   | shapeless: 1 to 9 ingredients | `shapeless recipes need 1 to 9 ingredients` |
   | every ingredient (map or list order, or `input`), each material in order | `unknown material <value>` or `unknown tag <value>` |
   | cooking types: `experience` is a number of at least 0 | `invalid experience` |
   | cooking types: `cooking-time` is a whole number of at least 1 | `invalid cooking time` |

   Values in reasons are shown as written in the file.
5. **Disabled vanilla recipes.** `disabled-vanilla` lists namespaced recipe keys such as
   `minecraft:torch` (without a namespace, `minecraft` is assumed). Each listed recipe that
   exists in the `minecraft` namespace is removed from the server. Anything else is reported
   as unknown and ignored. The plugin keeps every vanilla recipe it removed so that it can put
   exactly that recipe back later.

## Reload and commands

6. **Reload** unregisters every recipe the plugin registered, puts back every vanilla recipe it
   removed, re-reads `recipes.yml`, registers the valid recipes, removes the listed vanilla
   recipes and replies
   `Loaded <loaded> recipes, skipped <skipped>, disabled <disabled> vanilla recipes.`, then one
   line per skipped recipe in file order, `Skipped <id>: <reason>.`, then one line per unknown
   `disabled-vanilla` entry in list order, `Unknown vanilla recipe: <key>` (the key in
   `namespace:key` form). A recipe removed from the file is gone from the server after the
   reload; a vanilla recipe no longer listed can be crafted again.
7. One command, `/recipes`, with case-insensitive subcommands, all needing the permission
   `recipesmith.admin` (register it in `plugin.yml` with default `op`). Validation order: an
   unknown subcommand, or none, gets the general usage line; a wrong number of arguments gets
   the subcommand's usage line; then the permission is checked
   (`You do not have permission to do that.`); the first failure is the only reply.

   | Subcommand | Reply |
   | --- | --- |
   | `reload` | requirement 6 |
   | `list` | `Recipes (<n>):` then one line per loaded recipe sorted by id, `<id>: <type> -> <amount> <result>` with the result as its lower-case material key (`4 coarse_dirt`); with none, `No recipes.` |
   | `disable <key>` | `Disabled <key>.`; `<key> is already disabled.`; `Unknown vanilla recipe: <key>` |
   | `enable <key>` | `Enabled <key>.`; `<key> is not disabled.` |

   `disable` removes an existing `minecraft` recipe from the server and adds its key to
   `disabled-vanilla`; `enable` puts a recipe disabled by the plugin back and removes its key
   from the list. Both rewrite `recipes.yml` (keeping the recipes and every other key) and use
   the key in `namespace:key` form both in the file and in the replies. The usage lines are:

   ```text
   Usage: /recipes <reload|list|disable|enable>
   Usage: /recipes reload
   Usage: /recipes list
   Usage: /recipes disable <key>
   Usage: /recipes enable <key>
   ```

8. A permission-gated shaped or shapeless recipe remains registered. For each player's prepare
   event, players without the configured permission see no result and cannot take the output.
   Reload replaces the permission mapping with the mapping from the newly loaded file.

The hidden cases run against the real server and cover the default file, the command and
permission declarations, crafting every kind of recipe through the server (shape offsets,
material lists, tags, shapeless counts, result names and lore (including a tagged recipe with a
MiniMessage-named result), the cooking and stonecutting
recipe properties, smelting in a real furnace, the recipe keys, every validation reason in
order, reload removing and restoring recipes, disabling and enabling vanilla recipes, the list,
permission checks with limited senders and the usage lines.
