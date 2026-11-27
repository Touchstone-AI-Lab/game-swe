# Harbor workspace

The mod to repair is the source tree in `/app/mod`; the verifier grades that directory.

# DsMMO: skill handlers, saves and commands misbehave on a live server

## Context

`/app/mod` is **DsMMO** (Apache-2.0) by Jodli Developement. It is a
server-only Don't Starve Together mod inspired by McMMO. Players earn DsMMO
experience for actions such as chopping, mining, attacking, digging and
picking, and every level makes the skills of that action more likely to
trigger. `README.md` describes the skill trees. The server mod is
`modinfo.lua`, `modmain.lua` and the player component in
`scripts/components/`.

Our dedicated server runs the mod with its default settings.

## Reports from the server

> The log fills with Lua errors from the DsMMO player component whenever
> someone takes damage that no creature caused. Standing in the dark and
> getting hit by the darkness is the easiest way to reproduce it.

> A player with a high ATTACK level who hurts themselves gets chased by a
> Beetaliation bee that goes after the player themselves.

> Explosive touch sometimes throws a Lua error when a player attacks
> something that cannot take part in a fight.

> Ghosts get a Lua error from DsMMO when a haunt has no target.

> Woodie in werebeaver form digs without a tool, and every dig throws a Lua
> error from DsMMO.

> We changed the Exp-gain option and restarted the server. Players who had
> played before the change still show their old levels, which no longer
> match their experience under the new setting.

> A player whispered `#dsmmo eat` to try out Self-cannibalism before reading
> the help, and DsMMO threw a Lua error. The same happens when the stat to
> refill is left out.

> Everything else about the skills seems fine. Attacks and digs still earn
> experience, Beetaliation still sends a bee after creatures that attack a
> player, Explosive touch still hurts creatures, and Ghosty fireflies still
> turn a haunted evil flower into fireflies.

## Expected behaviour

- DsMMO never raises an error from its event handlers for any of the
  situations above. Whatever the skill rolls, the action or the damage goes
  ahead normally.
- Being attacked still earns one point of ATTACK experience, whether or not
  there is an attacker.
- Beetaliation only ever sends a bee after an attacker that is not the player.
  Damage with no attacker, and damage the player caused themselves, never
  spawns a bee. A creature that attacks the player can still trigger one
  bee, which targets that creature.
- Explosive touch only applies its extra damage to targets that can take
  part in a fight. Attacking anything else does nothing extra and raises no
  error. Creatures still take the extra damage.
- A haunt without a target does nothing and raises no error. Haunting an evil
  flower with Ghosty fireflies still replaces the flower with fireflies.
- Digging without a tool raises no error. Digging with a tool still earns one
  point of DIG experience, as before.
- A player's saved DsMMO data loads with the experience it was saved with. If
  it was saved under the same Exp-gain setting, its levels load as saved.
  If it was saved under another Exp-gain setting, every level, and the
  experience needed for the next level, is worked out again from the saved
  experience for the current setting.
- A `#dsmmo eat` command that is missing its action or its stat raises no
  error. The complete command, `#dsmmo eat [action] [health | hunger | sanity]`,
  still spends that action's experience to fill the stat, as the README
  describes.

## Evaluation

The verifier runs the mod on a real Don't Starve Together dedicated server
(Steam app 343050, build 24700372), offline, with the default settings. A
Wilson spawned on the server stands in for the player. The verifier raises
the player's DsMMO levels with the component's `set_level`, the same call the
mod's `dsmmo_set` command makes, and it makes every skill roll succeed. It
then pushes the game's own `attacked` and `performaction` events for the
situations above. It saves a player through its save record and loads that
record into another player, once unchanged and once marked as written under
another Exp-gain setting. It passes whispered `#dsmmo` commands to the
component's command handler as the mod's chat hook does, word by word. It
checks for errors, for the bees, damage and fireflies the skills produce, for
the refilled stat, and for the experience and levels recorded in the
player's save data.
