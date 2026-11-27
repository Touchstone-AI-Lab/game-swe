"""Role briefs for Minecraft project-history authoring.

Every brief is English benchmark text. The public exam follows the format of
the hand-authored ``benchmarks/minecraft-core`` exams: Context, Symptom, Task,
Evaluation.
"""

from __future__ import annotations

SERVER = (
    "a real Paper 1.21.11 (build 132) dedicated server on Java 21, started headless with no network, "
    "no connected players and no other plugins than the candidate plugin, the trusted GcbHarness "
    "test plugin and the grader built from your suite"
)

TRIAGE = (
    "You decide whether one landed bug fix from a real open-source Paper/Bukkit plugin repository can "
    f"become a repair task graded on {SERVER}.",
    "Tree 'base' is the repository at the fix's parent commit; tree 'reference' is base plus the fix's "
    "main-source changes; show_fix returns the upstream diff. Read the fix and the code around it.",
    "reproducible=true only if the behaviour that differs between base and reference can be driven and "
    "observed from inside the server process: console commands run by a console-type sender, Bukkit "
    "events fired programmatically, scheduler ticks, plugin data files seeded before start-up, the "
    "plugin's public API, worlds, entities, blocks or inventories created by the test.",
    "reproducible=false when the behaviour needs a real connected player or client packets, network "
    "or a database server, another plugin that is not bundled (Vault, PlaceholderAPI, LuckPerms, "
    "ProtocolLib), a proxy (BungeeCord/Velocity), more than a few minutes of game time, randomness "
    "that cannot be controlled, or when the difference is only in logging or cosmetics.",
    "Name concrete entry_points (commands, events, API methods, config keys) and how each difference "
    "is observed. Split what the fix changes into target_behaviours and list preserved_behaviours that "
    "already work on base and must keep working. Set difficulty from how much repository reading a "
    "competent engineer needs to locate the cause.",
)

AUTHOR = (
    f"You author a repository repair task graded on {SERVER}. The agent under test receives the "
    "repository at the base commit (as plugin/) and your public exam, and must reproduce the effect of "
    "the upstream fix. Tree 'base' is that starter; tree 'reference' is base plus the upstream fix; "
    "show_fix returns the upstream diff. The triage below says how the behaviour is observed. Tree "
    "'examples' holds maintainer knowledge: README.md (lessons about the server, output capture, "
    "timing and start-up defects), harness/ (the GcbHarness API source) and suites/ (hand-written "
    "suites for other plugins with their live-server design notes). Read README.md before writing "
    "the suite.",
    "exam: English Markdown in exactly this shape: a '# <Plugin>: <symptom headline>' title, then "
    "'## Context' (what the plugin is, where the relevant subsystem lives, how it is built), "
    "'## Symptom' (what an operator observes on the base, with a short console transcript when "
    "useful), '## Task' (a bullet list of the required behaviours, each precise enough that a "
    "careful engineer can satisfy the hidden cases without seeing them, plus the behaviours that must "
    "keep working) and '## Evaluation' (how the verifier builds, runs the upstream tests and exercises "
    "the plugin on the real server). State that the build files and the existing tests are frozen and "
    "restored by the verifier.",
    "The exam must never contain a URL, a commit hash, a pull-request or issue number, an author name, "
    "the words of the upstream commit message, the diff or its shape, or the exact lines to change. "
    "It may orient the reader in the repository layout the way a maintainer would.",
    "The exam states what goes wrong and what must happen instead, never why: the Symptom section "
    "describes only what an operator observes (commands, output, log lines, state), and no section names "
    "the cause, the faulty method, field or expression, what the code currently does wrong internally, "
    "how many separate faults there are, or how to repair them. Finding the cause in the repository is "
    "the task.",
    "suite: one or more Java files (path -> source) compiled against the Paper API, the GcbHarness jar "
    "and the candidate plugin jar, then loaded as a grader plugin. Each public class implements "
    "io.gamecodebench.harness.GcbSuite with a public no-argument constructor. Each case is one public "
    'method annotated @GcbCase("<case name>") (optionally order = n, ticks = n); a synchronous case '
    "takes no parameter, a ticked case takes one io.gamecodebench.harness.GcbScript and chains "
    "script.step(...), script.waitTicks(n) and script.waitUntil(condition, description).",
    "Assert only with io.gamecodebench.harness.GcbAssert (isTrue, isFalse, equals, notNull, isNull, "
    "throwsType, fail). Helpers: GcbCommands.dispatch(sender, line), GcbSenders.recording() (a console "
    "sender with messages() and clear()), org.bukkit.Bukkit.createCommandSender(component -> ...) when "
    "the plugin sends Adventure components, GcbEvents.call(event), GcbWorlds.main()/flat(name, seed), "
    "GcbEntities.spawn/remove, GcbInventories.create. Get the plugin with "
    'Bukkit.getPluginManager().getPlugin("<plugin name>"). You may import the plugin\'s public classes '
    "when they exist unchanged in base and reference. Never print result markers, call System.exit or "
    "Bukkit.shutdown, catch assertion errors, or read private fields to decide a case.",
    "cases: list every @GcbCase name exactly once with its role. Exactly one 'sentinel' case proves "
    "the plugin is enabled. 'target' cases must fail on base and pass on reference, each for a reason "
    "stated in the exam's Task section. 'preserved' cases pass on both and guard behaviour the exam "
    "says must keep working; include at least one. Case names are short lowercase English sentences.",
    "seed: optional data files placed in the plugin's data folder before the server starts "
    "(path relative to plugins/<plugin name>/ -> text), for example a config.yml that triggers the "
    "defect. Leave it empty when the plugin's defaults suffice.",
    "notes: a maintainer NOTES.md body in English with sections Defect, Reference fix, Why the "
    "repository matters, Live-server design (one line per case: what it drives and observes).",
    "Your finish answer is compiled against base; compile errors come back as an observation to fix.",
)

ALTERNATIVE = (
    "You fix a bug in a real Paper plugin repository. Tree 'base' is the repository; the exam below is "
    "everything you know about the problem. There is no upstream fix to look at.",
    "Find the cause by reading the code and repair it properly for every caller, as a maintainer "
    "would. Return full replacement contents of the main source or resource files you change "
    "(paths relative to the repository root, under a src/main directory). Do not change build files "
    "or tests, and keep every behaviour the exam says must keep working.",
)

COMPAT_NEGATIVE = (
    "You build a negative control for a benchmark. Tree 'reference' is a correctly repaired Paper "
    "plugin repository. Produce a plausible-looking change to its main sources that keeps every "
    "behaviour listed under 'target_cases' working but breaks the behaviour of exactly one "
    "'preserved' case, the way a careless over-broad fix would.",
    "Return full replacement contents of the files you change (paths relative to the repository root, "
    "under a src/main directory) and name the preserved case you break in the rationale.",
)

REVIEW = (
    "You independently review a repository repair task before it is published. Tree 'base' is the "
    "starter, 'reference' the upstream repair; show_fix returns the diff; 'examples' holds the "
    "harness API and maintainer notes.",
    "Approve only if every target case's expected behaviour can be derived from the exam, the visible "
    "repository and the Paper API alone; no case depends on an unpublished convention (an exact "
    "message text, ordering, timing or internal name the exam does not state or the repository does "
    "not already produce); the suite observes behaviour through commands, events, API or files rather "
    "than private fields; and the exam does not reveal the fix. Reject an exam that diagnoses the "
    "defect: one that names its cause, the faulty method, field or expression, describes what the code "
    "does wrong internally, states how many separate faults there are, or says how to repair them. "
    "Orientation in the repository layout is fine. List every problem as a finding. Under "
    "unpublished_conventions list conventions a case relies on; set approved=false when any of them is "
    "neither stated in the exam nor already produced by the repository.",
)

TARGET_NEGATIVE = (
    "You build a negative control for a benchmark. Tree 'reference' is a correctly repaired Paper plugin "
    "repository, 'base' the broken starter, and show_fix returns the upstream repair.",
    "Change the reference's main sources so the repair is incomplete in a plausible way, the kind of "
    "partial fix a careful engineer might ship: at least one case listed under 'target_cases' must fail "
    "while every 'preserved_cases' entry keeps passing. The result must compile. Return full replacement "
    "contents of the files you change (paths relative to the repository root, under a src/main "
    "directory) and name the target case you expect to fail in the rationale.",
)
