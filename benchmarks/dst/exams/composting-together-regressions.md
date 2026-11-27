# Composting Together: the compost pile misbehaves on a dedicated server

## Context

`/app/mod` is **Composting Together** (MIT), a Don't Starve Together mod from
the "Don't Starve Modding" group. It adds a craftable compost pile. You fill
the pile's five-slot container with spoiling food and garden waste and start
it, and after some in-game days it produces Manure (`poop`) that you harvest.
The mod's `README.md` describes the recipes, durations and bonuses. The
configuration options are in `modinfo.lua`, and `modmain.lua` turns them into
`TUNING` values.

Our dedicated server runs the mod with its default settings, except that
**Attract Fireflies** (`spawn_fireflies`) is set to `always`.

## Reports from the server

> The compost pile's crafting recipe shows no ingredient amounts, and players
> say they can build it for free.

> Compost is ready within a minute instead of taking days.

> When we inspect a pile whose compost is ready, the game says the pile is
> empty.

> Filling a pile with a lot of rotten vegetables, enough for the "fertile
> soil" upgrade, makes starting the compost fail with a Lua error. The pile
> then stays in a broken state. It works in a game hosted from a client.

> Harvesting a finished pile hands over the manure and then throws a Lua
> error. After that the pile can never be opened again.

> A batch of rotten vegetables pays the rotten-food bonus, which is fine. But
> the next batch pays that bonus again, even when it had nothing perishable in
> it.

> After a server restart, finished piles no longer offer the Harvest action.
> Piles that were empty before the restart turn into "finished" piles with
> manure to harvest shortly after loading, and they cannot be opened.

## Expected behaviour

- With the default settings the compost pile recipe costs 6 Rocks, 3 Logs and
  4 Manure. These are the amounts the mod's settings define.
- Composting times follow the configured duration (default): a batch that
  only makes the basic recipe, such as three Twigs, takes three in-game days.
  It is not ready after two and a half days, and it is ready once three days
  have passed.
- A pile needs at least three items before it can start composting.
- Inspecting a pile whose compost is ready reports the `DONE` status. While a
  batch that earned the fertile-soil upgrade is composting, inspecting it
  reports `COMPOSTING_FERTILE`.
- No step of the pile raises an error on a dedicated server, which has no
  local player: starting a batch that earns the fertile-soil upgrade, and
  harvesting while fireflies are attracted, both complete normally.
- Harvesting a finished pile gives the harvester the manure (two Manure for a
  basic batch). Afterwards the pile is empty, no longer offers a harvest, and
  can be opened and filled again.
- The rotten-food bonus described in the README applies only to the batch that
  earned it. For example, a batch of three nearly rotten Carrots yields six
  Manure, and a following batch of three Twigs yields the basic two.
- Save and load (a server restart) keep the pile's state. A pile in the middle
  of composting still finishes when its remaining time has passed. A finished
  pile still offers the Harvest action. An empty pile stays empty, does not
  become finished, and can still be opened.

## Evaluation

The verifier runs the mod on a real Don't Starve Together dedicated server
(Steam app 343050, build 24700372), offline, with the configuration above. A
Wilson spawned on the server stands in for the player. The verifier fills
piles through their container. It starts composting with the mod's `COMPOST`
action and harvests with the `HARVEST` action. It lets in-game time pass
through the entity long-update path the server uses to catch up on elapsed
time. It saves and reloads piles through their save records. It checks the
recipe, the inspection status, the actions a pile offers, the manure handed
to the player, and whether the pile can be opened.
