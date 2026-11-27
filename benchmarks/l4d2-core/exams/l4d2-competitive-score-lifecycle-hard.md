# Competitive Rework: score lifecycle regressions

The source-only Competitive Rework repository is at `/app/l4d2-competitive`.
Operators report inconsistent scores from its **L4D2 Scoremod+ / ZoneMod hybrid
score** plugin (`l4d2_hybrid_scoremod_zone.sp`). Repair the following release
contract while preserving the public `SMPlus_*` natives, plugin identity,
Left4DHooks/L4D2Lib integration, existing scoring formula for ordinary settings,
and other plugins in the repository.

1. **Ineligible survivors contribute to live bonuses.** A dead Survivor whose
   incapacitated flags have cleared still increases the damage-bonus survival
   multiplier. A ledge-hanging or falling-from-ledge Survivor can still contribute
   carried pills. Health, damage and pills bonuses must consistently exclude dead,
   incapacitated, hanging and falling Survivors. Preserve the existing first
   `survivor_limit` roster selection, permanent-health treatment after an
   incapacitation, and ordinary living/upright scoring.

2. **Live configuration is partly stale.** Changes to the bonus multiplier,
   permanent-health proportion, pills factor, pills maximum and survivor limit
   must all take effect without a map reload. Recalculate dependent maxima, unit
   values and carried-pill values together, but do not erase already incurred
   temporary-health losses. Preserve the existing ordinary formula and final
   integer flooring exposed by `SMPlus_*`.

3. **Boundary configurations produce invalid scores.** A permanent proportion of
   `0` means all damage bonus, and `1` means all permanent-health bonus. Neither may
   divide by zero during config, incapacitation, death, or score reporting. Clamp
   the effective proportion to `[0,1]`, use a nonnegative effective map multiplier,
   and an effective survivor limit of `max(1, configured survivor_limit)` for
   roster selection, maxima and divisor calculations. At proportion `0`, use 100
   temporary-health units per configured Survivor; at `1`, the damage pool and
   temporary unit worth are zero. Between those endpoints retain the current
   formula. A nonpositive pills factor or maximum disables carried-pill bonus;
   a positive maximum below five is itself the cap. A zero map bonus gives zero
   carried-pill bonus. Normal pill rounding to the nearest multiple of five is
   preserved, with the usual minimum five only when the positive cap permits it.
   All public maxima and live bonuses must be finite, nonnegative integers.

4. **The alternate-damage forward can mint or misattribute bonus.**
   `L4D2_ADM_OnTemporaryHealthSubtracted(client, oldHealth, newHealth)` is the
   existing compatibility boundary. Accept only a living upright Survivor in an
   open round, and only a positive decrease after clamping each reported health
   to at least zero. Healing, equal values, invalid/disconnected clients, other
   teams and terminal states must not change the loss ledger. Keep valid ordinary
   deductions and the existing tiebreak accounting; do not remove compatibility.

5. **Ledge recovery refunds unrelated losses.** A ledge-grab event debits its
   nonnegative pre-incap temporary health once per outstanding ledge episode.
   A `revive_success` with `ledge_hang=true` may refund at most that episode's
   debit and at most the Survivor's currently quantized temporary health when
   the existing deferred frame callback settles. Duplicate grab/revive events
   must not create extra debit/refund. Ordinary ground revives never refund a
   ledge episode. The deferred refund must belong to the same connected client,
   team/round half and round generation; a disconnected/replaced client (including
   a client whose disconnect has already been queued), team
   switch, death, new round or later ledge must not receive an old refund. Continue
   deferring until the frame after revival rather than reading stale event-time
   health. Preserve the existing temporary-health quantization:
   `max(0, ceil(buffer - elapsed * pain_pills_decay_rate) - 1)`.

6. **Round boundaries leak or erase ledger state.** A new round starts with zero
   loss and tiebreak ledger for its own half, clears outstanding per-client health
   snapshots and ledge work, and retains the other half's completed state. Client
   disconnect must clear that client's snapshots. Once the existing end-round
   forward has finalized a round, later damage, incapacitation, death, ledge or
   alternate-damage callbacks must not alter its scoring state. Config refreshes
   remain independent of round reset. Keep the existing one-shot finalization.

7. **Unloading loses the operator's server settings.** The plugin temporarily
   owns `vs_survival_bonus` and `vs_tiebreak_bonus`. On unload it must restore the
   exact values present when this plugin instance started, including after
   recalculation or end-round scoring. Restoring engine defaults is wrong. A later
   reload must capture that new instance's own baseline; do not share stale state
   across loads.

These are authored intended behaviors over the frozen existing plugin, not a
request to reproduce a particular upstream patch. Avoid changing unrelated score
policy, the other scoremod variants, or plugin APIs. Keep GPL attribution and
source only; no compiled plugins, game binaries, archives, symlinks or Git metadata.
Do not modify `/tests`.

Run `python3 tools/smoke.py` after editing. The private offline verifier recompiles
the submitted plugin and boots the pinned real L4D2 server with Left4DHooks and
L4D2Lib. It observes public native results, game properties, ConVars and complete
event/deferred-frame sequences using real engine client entities. It does not
compare patches or require private helper names. Runtime setup failures cannot pass.
