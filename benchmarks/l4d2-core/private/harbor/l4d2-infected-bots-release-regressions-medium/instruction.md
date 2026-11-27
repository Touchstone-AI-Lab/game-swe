# L4D Infected Bots release regressions

The repository is a source-only snapshot of L4D Infected Bots and its required
public-source plugin and compile dependencies from `fbef0102/L4D1_2-Plugins`
commit `b570e9efd9534ea8822f6fc7909704b4ee8fcdf2`. Compiled plugins and Valve game
files are intentionally absent. Repair the regressions in the submitted source;
do not replace the project with a smaller implementation.

Run the public compile check with:

```bash
python3 tools/smoke.py
```

The repaired plugin must satisfy all of these observable contracts:

1. **Server-capacity accounting.** `sm_zlimit` must clamp the requested special
   infected limit to the number of actual free client slots:
   the running server's client capacity minus its current survivor clients. It
   must not reserve a phantom extra slot. The applied value must remain visible through
   `L4DInfectedBots_GetConfigInt("max_specials")`.
2. **Configuration profiles and reload.** The selected data file first resolves
   a Settings profile from `Settings/default` plus the matching alive-survivor
   count entry; omitted count keys inherit `Settings/default`. If the current
   map has a `Maps/<map>` profile, that map profile becomes active and is
   resolved from `Maps/<map>/default` plus its matching survivor-count entry;
   omitted map-count keys inherit the map default. Without a current-map entry,
   the resolved Settings profile remains active. Changing
   `l4d_infectedbots_read_data` reloads the selected profile. Values set by both
   `sm_zlimit` and `sm_timer` are temporary and must be replaced by the newly
   loaded data. Integer, float, and string settings must follow these profile
   rules.
3. **Initial spawn timing.** The initial wave waits `initial_spawn_time` from
   its scheduling request. While that wave is pending, an infected death must
   not enqueue a normal bot or coop-versus replacement that advances the wave's
   deadline. Reusing the already queued initial wave is valid: a death does not
   restart its countdown. A newly scheduled initial replacement uses the initial
   delay rather than the normal respawn calculation. After the initial window
   ends, ordinary deaths must again use the configured normal respawn delay.
4. **Finale cleanup.** `finale_win` is a round-ending event, including on custom
   finales that never fire `finale_vehicle_leaving`. It must transition the
   plugin to the ended state and prevent pending bot/refill work from
   replenishing special infected after the win. Disabling and re-enabling the plugin
   through its public allow cvar must remain error-free and preserve this
   behavior.

Keep the public native declarations compatible, and do not add compiled `.smx`
files, Valve content, credential material, executable network-client helpers, or
verifier-specific output.
Reasonable refactors are accepted; scoring observes public native results and
real dedicated-server behavior rather than private helper names or a reference
diff.
