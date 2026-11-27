# Renewable Polish — public contract v2

Authored difficulty: **medium**; calibration: **unmeasured / 待校准**. Repair mod `isolated_card_wear_v2`, prefix `icw2`, enhancement `m_icw2_polish` and ordinary single-use Tarot `c_icw2_applicator` (cost $3). This is an authored exercise, not a historical upstream bug.

1. Each newly polished physical playing card has **two uses**. Each time that card actually scores as a played card, it contributes **+20 Chips** and consumes exactly one use. Holding, discarding, dealing, description queries and changing blinds neither consume nor replenish uses.
2. The second use still contributes the full +20 Chips. After that scoring, change that same physical card to ordinary unenhanced `c_base`, preserving identity, rank and suit. Later scoring receives no polish bonus unless the card is polished again.
3. Uses belong to individual physical cards. Several polished cards may score in the same hand; each gets its own reward and consumes only its own use. Older cards must not mutate defaults for other or future cards.
4. During SELECTING_HAND, the applicator can target exactly one currently ordinary card **or one card already carrying this polish**, including a partially worn card. A real Use consumes the Tarot through normal engine lifecycle and resets the selected card to **exactly two fresh uses**, independent of its previous remaining uses or prior exhaustion. Reapplication does not add old uses, retain stale wear or change another card. It preserves target identity/rank/suit and grants no immediate chip, money or card reward.
5. While polished, expose the numeric remaining count through pure `loc_vars(...).vars[1]`, as in the starter. Once ordinary, use the ordinary description with no polish counter. Internal state layout is unrestricted; description reads are not scoring or application events.

Scope: normal seeded gameplay, ordinary rank/suit cards, native scoring, real applicator use and normal round/deal transitions. Copying, retriggers, debuffs, editions, save restoration and interaction with other enhancements are excluded. No global card or enhancement prototype may be changed as an effect of one instance's wear.

Editable files: `main.lua` and `lib/wear.lua`; the manifest is fixed. Do not modify fixtures, observers, runtime, dependencies or external state. The two files separate engine registration/contexts from wear/application logic; equivalent internal designs within the file allowlist are accepted. Private trajectories, exact scores, reference implementations and logs are not public materials.
