from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["construct", "repair"]


@dataclass(frozen=True)
class StudyTask:
    """One registered task of the audited inventory.

    ``app_subdir`` is where a task's own ``solution/solve.sh`` expects the
    submission below ``/app``; ``submission_is_app`` says whether the evaluated
    submission is ``/app`` itself (the pack ships a named source tree inside the
    workspace) or that subdirectory (the pack evaluates the source root directly).
    ``reference_overlay`` replaces that oracle for a pack whose reference does not
    match the Hub workspace layout: ``(source, target)`` copies ``solution/<source>``,
    a file or directory, over ``<target>`` below the submission. ``reference_tree`` is for a
    pack that keeps its reference outside ``private/harbor``: ``(source, target)`` copies the
    directory ``source``, relative to the pack root, over ``<target>`` below the submission.
    """

    game: str
    pack: str
    task: str
    kind: Kind
    source_family: str
    pack_dir: str
    app_subdir: str
    submission_is_app: bool
    reference_overlay: tuple[str, str] | None = None
    reference_tree: tuple[str, str] | None = None

    @property
    def key(self) -> str:
        return f"{self.game}/{self.pack}/{self.task}"


def _balatro(task: str) -> StudyTask:
    # Each task is a separately authored repair. Its frozen gold control is the reference.
    reference = (f"private/native-v1/controls/{task}/gold", "starter")
    return StudyTask(
        "balatro", "core", task, "repair", f"balatro:{task}", "balatro", "starter", True, None, reference
    )


def _dst(task: str, family: str) -> StudyTask:
    return StudyTask("dst", "core", task, "repair", family, "dst", "mod", True)


def _dst_construct(task: str) -> StudyTask:
    return StudyTask("dst", "construct", task, "construct", f"dst:{task}", "dst-construct", "mod", False)


def _gmod(task: str) -> StudyTask:
    return StudyTask("garrys-mod", "addons", task, "construct", f"gmod:{task}", "gmod", "addon", False)


def _mindustry_construct(task: str) -> StudyTask:
    family = f"mindustry:{task}"
    pack_dir = "mindustry-construct"
    return StudyTask("mindustry", "construct", task, "construct", family, pack_dir, "mindustry", False)


def _minecraft_construct(task: str) -> StudyTask:
    family = f"minecraft:{task}"
    pack_dir = "minecraft-construct"
    return StudyTask("minecraft", "construct", task, "construct", family, pack_dir, "plugin", True)


def _palworld(task: str) -> StudyTask:
    return StudyTask("palworld", "core", task, "construct", f"palworld:{task}", "palworld", "mod", False)


def _darkrp(task: str) -> StudyTask:
    return StudyTask("garrys-mod", "darkrp", task, "repair", "darkrp", "darkrp-core", "darkrp", True)


def _gmod_addon(task: str, family: str, subdir: str) -> StudyTask:
    return StudyTask(
        "garrys-mod", "addon-repairs", task, "repair", family, "gmod-addon-repairs", subdir, True
    )


def _isaac(task: str) -> StudyTask:
    return StudyTask("isaac-rebirth", "core", task, "repair", "exodus", "isaac-core", "exodus", True)


def _isaac_synth(task: str) -> StudyTask:
    # Clean-room construct tasks: the reference is one file that replaces the empty main.lua.
    return StudyTask(
        "isaac-rebirth", "synth", task, "construct", f"isaac-synth:{task}", "isaac-synth", "mod", True,
        reference_overlay=("reference.lua", "mod/main.lua"),
    )


def _l4d2(task: str, family: str, subdir: str) -> StudyTask:
    return StudyTask("left-4-dead-2", "core", task, "repair", family, "l4d2-core", subdir, True)


def _stardew_generation(task: str, family: str) -> StudyTask:
    return StudyTask("stardew-valley", "core", task, "construct", family, "stardew-core", "mod", True)


def _stardew(task: str, family: str) -> StudyTask:
    return StudyTask("stardew-valley", "core", task, "repair", family, "stardew-core", "StardewMods", True)


def _mindustry(task: str) -> StudyTask:
    return StudyTask(
        "mindustry", "mindustry-core", task, "repair", "mindustry", "mindustry-core", "mindustry", True
    )


def _minecraft(task: str, family: str) -> StudyTask:
    return StudyTask("minecraft", "core", task, "repair", family, "minecraft-core", "plugin", True)


def _rimworld(task: str, subdir: str) -> StudyTask:
    return StudyTask("rimworld", "core", task, "repair", subdir.casefold(), "rimworld-core", subdir, True)


def _slay_the_spire(task: str) -> StudyTask:
    return StudyTask(
        "slay-the-spire", "core", task, "repair", "modthespire", "slay-the-spire-core", "modthespire", True
    )


def _slay_the_spire_native(task: str, family: str) -> StudyTask:
    # The Hub workspace holds the starter as project/; the Harbor oracle writes into a named
    # /app directory instead, so the study copies solution/after over project/ directly.
    return StudyTask(
        "slay-the-spire", "core", task, "repair", family, "slay-the-spire-core", "project", True,
        reference_overlay=("after", "project"),
    )


def _terraria(task: str, starter: str) -> StudyTask:
    # The workspace root holds the frozen mod tree under its starter name; the oracle
    # writes into /workspace/<starter>, which the study relocates to the control root.
    family = f"terraria:{starter}"
    return StudyTask("terraria", "core", task, "repair", family, "terraria-core", starter, True)


# Every task the Hub can evaluate on this project's reference host. Repairs come first and
# construction tasks close the list. Palworld's attempts were once generated here and
# evaluated on a Windows host (StudyConfig.deferred_evaluation); its native Linux runtime now
# runs here. The six game-backed Slay the Spire native tasks run on the Steam runtime
# `slay-the-spire/sts-native-646570-build10180494`, and the eight Isaac construct tasks on
# `isaac-rebirth/afterbirth-plus-1.06.t1-synth`. Balatro's reviewed Linux runtime executes
# only source-reviewed bytes, so its E1 studies defer evaluation until each generated
# submission is reviewed. mts-enum-identity-r2 has no runtime binding and is not registered.
# Minecraft uses the pinned official-download Paper runtimes for its repair and construct packs.
TASKS: tuple[StudyTask, ...] = (
    _dst("dst-fixed-bundle-regressions", "dst-fixed"),
    _dst("dst-fixed-module-regressions", "dst-fixed"),
    _dst("composting-together-regressions", "composting-together"),
    _dst("dsmmo-release-regressions", "dsmmo"),
    _dst("glassic-api-regressions", "glassic-api"),
    _darkrp("darkrp-release-regressions-v3"),
    _darkrp("darkrp-live-server-regressions"),
    _darkrp("darkrp-door-economy-regressions"),
    _darkrp("darkrp-core-library-regressions"),
    _darkrp("darkrp-registration-regressions"),
    _darkrp("darkrp-money-regressions"),
    _darkrp("darkrp-persistence-regressions"),
    _gmod_addon("advdupe2-paste-regressions", "advdupe2", "advdupe2"),
    _gmod_addon("cfw-contraption-regressions", "cfw", "cfw"),
    _gmod_addon("starfallex-library-regressions", "starfallex", "starfallex"),
    _gmod_addon("wiremod-e2-library-regressions", "wiremod", "wire"),
    _gmod_addon("wiremod-gates-chips-regressions", "wiremod", "wire"),
    _isaac("isaac-exodus-release-regressions"),
    _isaac("isaac-exodus-tear-trajectory"),
    _isaac("isaac-exodus-active-item-state"),
    _isaac("isaac-exodus-orphaned-effects"),
    _isaac("isaac-exodus-projectiles-and-targets"),
    _isaac("isaac-exodus-room-floor-state"),
    _isaac("isaac-exodus-numeric-arithmetic"),
    _isaac("isaac-exodus-passive-reshapers"),
    _isaac("isaac-exodus-callback-wiring"),
    _isaac("isaac-exodus-mixed-triage"),
    _l4d2("l4d2-competitive-release-regressions-easy", "competitive-rework", "l4d2-competitive"),
    _l4d2("l4d2-left4dhooks-api-regressions-medium", "left4dhooks", "left4dhooks"),
    _l4d2("l4d2-infected-bots-release-regressions-medium", "infected-bots", "l4d1_2_plugins"),
    _l4d2("l4d2-linge-release-regressions-hard-v3", "linge", "linge-hud"),
    _l4d2("l4d2-mutant-tanks-release-regressions-hard", "mutant-tanks", "mutant-tanks"),
    _l4d2("l4d2-linge-director-state-hard", "linge", "linge-hud"),
    _l4d2("l4d2-competitive-score-lifecycle-hard", "competitive-rework", "l4d2-competitive"),
    _l4d2("l4d2-vslib-scheduler-persistence-hard", "linge", "linge-hud"),
    _l4d2("l4d2-confogl-cvar-transactions-hard", "competitive-rework", "l4d2-competitive"),
    _l4d2("l4d2-library-map-tank-state-hard", "competitive-rework", "l4d2-competitive"),
    _stardew("stardew-automate-minifridge-storage", "automate"),
    _stardew("stardew-automate-zero-stack-output", "automate"),
    _stardew("stardew-automate-release-regressions", "automate"),
    _stardew("stardew-automate-release-regressions-v2", "automate"),
    _stardew("stardew-automate-release-regressions-v3", "automate"),
    _stardew("stardew-automate-output-count-drift", "automate"),
    _stardew("stardew-cp-release-regressions", "content-patcher"),
    _stardew("stardew-cjb-cheats-regressions", "cjb-cheats-menu"),
    _stardew("stardew-tractor-attachment-regressions", "tractor-mod"),
    _mindustry("logic-processor-regressions"),
    _mindustry("server-console-regressions"),
    _mindustry("defense-and-heat-regressions"),
    _mindustry("payload-and-save-regressions"),
    _mindustry("data-patch-regressions"),
    _minecraft("multiverse-core-case-insensitive-world-names", "multiverse-core"),
    _minecraft("chatty-bad-channel-disables-plugin", "chatty"),
    _minecraft("betterteams-help-page-bounds", "betterteams"),
    _minecraft("prometheus-exporter-players-total-main-thread", "prometheus-exporter"),
    _minecraft("chatty-reload-ignores-chat-commands", "chatty"),
    _minecraft("multiverse-core-world-exists-by-key", "multiverse-core"),
    _minecraft("betterteams-description-tag-injection", "betterteams"),
    _minecraft("chatty-reload-leaks-threads", "chatty"),
    _minecraft("chatty-failed-migration-dead-plugin", "chatty"),
    _minecraft("chatty-v2-migration-null-spy-format", "chatty"),
    _balatro("growth-v2"),
    _balatro("reversible-hand-limit-v1"),
    _balatro("seeded-effect-stream-v1"),
    _balatro("bounded-generator-v2"),
    _balatro("deck-removal-consistency-v2"),
    _balatro("live-joker-adjacency-v2"),
    _balatro("isolated-card-wear-v2"),
    _balatro("durable-charge-v2"),
    _balatro("shop-price-coherence-v2"),
    _balatro("pack-choice-commit-v2"),
    _rimworld("r4-uncraftable-material-basis", "R4"),
    _rimworld("r4-small-bench-ingredient-consumption", "R4"),
    _rimworld("project-rimfactory-cultivator-environment", "ProjectRimFactory"),
    _rimworld("combat-readiness-colony-wealth", "CombatReadinessCheck"),
    _rimworld("customize-weapon-ability-tracker", "CustomizeWeapon"),
    _rimworld("total-control-vanilla-gear-generation", "TotalControl"),
    _rimworld("bill-autopilot-repeat-mode-ownership", "BillAutopilot"),
    _rimworld("playwright-nonbulk-trade-accounting", "Playwright"),
    _rimworld("research-organized-tab-state", "ResearchOrganized"),
    _rimworld("adaptive-storage-slot-limit-restore", "AdaptiveStorage"),
    _slay_the_spire_native("basemod-dynamic-descriptions-r2", "basemod"),
    _slay_the_spire_native("stslib-block-ledger-r1", "stslib"),
    _slay_the_spire_native("stslib-icon-layout-r1", "stslib"),
    _slay_the_spire_native("downfall-stasis-lifecycle-r1", "downfall"),
    _slay_the_spire_native("basemod-phase-transitions-r1", "basemod"),
    _slay_the_spire_native("downfall-socket-flow-r3", "downfall"),
    _slay_the_spire_native("mts-enum-identity-r3", "modthespire"),
    _slay_the_spire_native("mts-load-order-regressions-r2", "modthespire"),
    _slay_the_spire_native("mts-mod-identity-regressions-r2", "modthespire"),
    _terraria("terraria-magic-storage-compressed-io-regressions-hard", "magic-storage"),
    _terraria("terraria-fargos-enchanted-tree-transactions-hard", "fargos-mutant"),
    _terraria("terraria-overhaul-entity-chunk-lifetime-hard", "terraria-overhaul"),
    _terraria("terraria-improvegame-space-wand-authority-hard", "improvegame"),
    _terraria("terraria-spirit-branching-quest-replication-hard", "spirit-mod"),
    _terraria("terraria-modliquid-map-persistence-hard", "mod-liquid-lib"),
    _terraria("terraria-aequus-carpentry-replication-hard", "aequus"),
    _terraria("terraria-starlight-ability-state-hard", "starlight-river"),
    _terraria("terraria-fargos-toggle-presets-hard", "fargos-souls"),
    _terraria("terraria-calamity-overhaul-time-replication-hard", "calamity-overhaul"),
    _dst_construct("camp-supply-ledger"),
    _dst_construct("container-transfer-transaction"),
    _dst_construct("rescue-dispatch-queue"),
    _dst_construct("world-rule-ballot"),
    _dst_construct("combat-target-arbiter"),
    _dst_construct("waystone-route-network"),
    _dst_construct("status-effect-stack"),
    _dst_construct("fuel-ration-allocator"),
    _dst_construct("trade-escrow-exchange"),
    _dst_construct("loot-roll-arbiter"),
    _stardew_generation("stardew-summon-horse-anywhere", "stardew:summon-horse"),
    _stardew_generation("stardew-auto-workshop", "stardew:auto-workshop"),
    _gmod("prop-ownership-quota-registry"),
    _gmod("staged-prop-alignment"),
    _gmod("persistent-loadout-profiles"),
    _gmod("hot-object-round-controller"),
    _gmod("contraption-blueprint-duplicator"),
    _mindustry_construct("transactional-core-router"),
    _mindustry_construct("build-quota-auditor"),
    _mindustry_construct("unit-lease-scheduler"),
    _mindustry_construct("power-grid-controller"),
    _mindustry_construct("wave-threat-arbiter"),
    _mindustry_construct("item-reservation-ledger"),
    _mindustry_construct("wave-budget-planner"),
    _mindustry_construct("logic-link-registry"),
    _mindustry_construct("core-failover-coordinator"),
    _mindustry_construct("blueprint-layout-reconciler"),
    _minecraft_construct("coinledger-bank-ledger"),
    _minecraft_construct("blocktrail-block-log-rollback"),
    _minecraft_construct("towncrier-timed-announcements"),
    _minecraft_construct("wardstone-region-protection"),
    _minecraft_construct("recipesmith-config-recipes"),
    _palworld("guild-storage-ledger"),
    _palworld("base-containment-mincut"),
    _palworld("raid-dispatch-queue"),
    _palworld("server-rule-ballot"),
    _palworld("guild-draft-canonical-order"),
    _palworld("outbox-receipt-recovery"),
    _palworld("pal-workforce-optimal-matching"),
    _palworld("raid-event-watermark"),
    _palworld("guild-consistent-checkpoint"),
    _palworld("world-epoch-fenced-timers"),
    _isaac_synth("construct-room-rng"),
    _isaac_synth("construct-config-navigation"),
    _isaac_synth("construct-config-persistence"),
    _isaac_synth("construct-hud-compositor"),
    _isaac_synth("construct-legacy-hud-lifecycle"),
    _isaac_synth("construct-option-rendering"),
    _isaac_synth("construct-entity-cleanup"),
    _isaac_synth("construct-callback-transaction"),
)

BY_KEY = {task.key: task for task in TASKS}


def task_for(key: str) -> StudyTask:
    try:
        return BY_KEY[key]
    except KeyError as error:
        raise ValueError(f"not a registered study task: {key}") from error
