from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameAuthoringSpec:
    game_id: str
    plugin_id: str
    pack_directory: str
    starter_directory: str
    runtime_id: str | None
    project_requirements: tuple[str, ...]
    verifier_requirements: tuple[str, ...]
    generation_contract: tuple[str, ...]
    verifier_contract: tuple[str, ...] = ()
    interface_requirements: tuple[str, ...] = ()
    # Every generated implementation path must start with one of these
    # prefixes when the tuple is non-empty (build files and stray roots are
    # rejected before any model repair loop).
    project_path_prefixes: tuple[str, ...] = ()
    # (regular expression, finding) pairs applied to every generated
    # implementation and model-authored verifier source file.
    source_lint: tuple[tuple[str, str], ...] = ()
    # The operator-rendered shell runner, when the game has one; it must
    # declare EXPECTED=<count> matching the structured case IDs.
    trusted_shell_runner: str | None = None
    # The verifier files the model authors itself; empty means every
    # verifier requirement is model-authored.
    model_authored_verifier: tuple[str, ...] = ()

    @property
    def generated_verifier_requirements(self) -> tuple[str, ...]:
        # The operator renders the trusted shell runner for games that declare
        # model_authored_verifier; the model authors only the behavioral suite.
        return self.model_authored_verifier or self.verifier_requirements


# Forbidden constructs in generated Minecraft sources: server internals the
# clean-room build cannot compile against, and calls that would end the
# verifier's server process before its result envelope is written.
MINECRAFT_SOURCE_LINT: tuple[tuple[str, str], ...] = (
    (r"\bnet\.minecraft\.", "net.minecraft internals are not public plugin API"),
    (r"\borg\.bukkit\.craftbukkit\b", "org.bukkit.craftbukkit internals are not public plugin API"),
    (r"\bSystem\s*\.\s*exit\s*\(", "System.exit would terminate the verifier server"),
    (r"\bBukkit\s*\.\s*shutdown\s*\(", "Bukkit.shutdown would terminate the verifier server"),
    (r"\bgetServer\s*\(\s*\)\s*\.\s*shutdown\s*\(", "Server.shutdown would terminate the verifier server"),
    (
        r"\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*(?:halt|exit)\s*\(",
        "Runtime.halt/exit would terminate the verifier server",
    ),
)


GAME_SPECS = {
    "dst": GameAuthoringSpec(
        game_id="dst",
        plugin_id="dst",
        pack_directory="dst-synth",
        starter_directory="mod",
        runtime_id=None,
        project_requirements=("modinfo.lua", "modmain.lua"),
        verifier_requirements=("hidden.lua", "server.lua"),
        generation_contract=(
            "Produce a complete Don't Starve Together server mod rooted at the workspace.",
            "Use Lua compatible with the pinned dedicated server and only documented base-game APIs.",
            "Declare exact scripts-relative require identifiers and public mod RPC/event names; "
            "modmain.lua must register the intended behavior on the master simulation.",
        ),
        verifier_contract=(
            "The hidden.lua sandbox executes the file immediately and requires its return value to be "
            "{cases = {{name = 'case-id', passed = true, message = 'ok'}, ...}}. "
            "It must not return a function and must report every case even after an assertion fails.",
            "hidden.lua can call load_submission('relative/path.lua', bindings) to execute a submitted "
            "Lua file and obtain its return value. Standard safe Lua globals are present; bindings may "
            "supply public game API test doubles, but require, dofile, loadfile, io, os, package, debug "
            "and Python are unavailable. It cannot load arbitrary paths or read source text.",
            "server.lua must return function(context) ... end. The evaluator loads it as a module "
            "inside the mod and calls it after the real master-simulation world boots. "
            "Use context.world and context:case('case-id', function() assert(...) end) for each case. "
            "context has exactly those two members and nothing else: there is no "
            "context:chat_messages, context:is_module_loaded, context.mod or any other helper, so "
            "observe behavior through context.world, real game globals and the submission's own "
            "public entrypoints. "
            "The evaluator catches each body error and serializes results; do not print a forged "
            "result marker or return your own case table from server.lua.",
            "server.lua must execute exactly all VerifierBundle.case_ids once, including a real "
            "mod-loaded sentinel. capsule_cases refer to server.lua case IDs, not hidden-only cases. "
            "Use the shared contract's real entrypoints; hidden sandbox doubles are diagnostic only "
            "and cannot replace any real dedicated-server assertion.",
        ),
    ),
    "stardew-valley": GameAuthoringSpec(
        game_id="stardew-valley",
        plugin_id="stardew-valley",
        pack_directory="stardew-synth",
        starter_directory="mod",
        runtime_id="stardew-1.6.15-smapi-4.1.10-synth",
        project_requirements=("Directory.Build.props", "Synthetic.sln"),
        interface_requirements=("Synthetic.csproj", "manifest.json"),
        verifier_requirements=("tests/test.sh", "tests/TaskSuite.cs"),
        model_authored_verifier=("tests/TaskSuite.cs",),
        trusted_shell_runner="tests/test.sh",
        generation_contract=(
            "Produce a complete anonymous SMAPI C# solution. Returned file paths are relative to "
            "the mod root: Synthetic.sln, Synthetic.csproj, Directory.Build.props and manifest.json "
            "are root-level files with no mod/ prefix. The solution must reference Synthetic.csproj.",
            "Target Stardew Valley 1.6.15, SMAPI 4.1.10 and net6.0; the container has the .NET 8 SDK.",
            "Use local game assembly references from $(GamePath), default /opt/stardew, and ensure "
            "the SMAPI manifest EntryDll exactly matches the generated project's built assembly. "
            "No NuGet downloads or external mods may be needed during evaluation.",
            "The C# project must explicitly reference $(GamePath)/Stardew Valley.dll, "
            "$(GamePath)/StardewModdingAPI.dll and $(GamePath)/MonoGame.Framework.dll with Private=false. "
            "Reference StardewValley.GameData.dll, xTile.dll, Netcode.dll and "
            "SMAPI.Toolkit.CoreInterfaces.dll from that same directory when present, using "
            "Exists(...) conditions, as the supplied trusted harness does. Microsoft.Xna.Framework "
            "types such as Point, Vector2 and Rectangle require the MonoGame.Framework reference.",
            "Set AppendTargetFrameworkToOutputPath=false and ProduceReferenceAssembly=false, with "
            "flat Release output under bin/Release. Copy manifest.json to output via "
            "CopyToOutputDirectory=PreserveNewest so the shell can deploy a complete mod. "
            "Use no PackageReference dependencies. Runtime rsync removes cached obj directories; "
            "the verifier may perform an offline restore using locally installed framework packs "
            "before building, without downloading game assemblies or changing the project.",
            "Every behavior must be reachable in the live mod: specify and implement an actual "
            "registered game event, input handler or neutral console command from ModEntry.Entry. "
            "An empty Entry with disconnected public helper methods is not a complete mod. "
            "Name the exact hook/command, its arguments and visible result in the interface contract; "
            "do not invent an unspecified menu or assume another mod calls the service. "
            "Any public test API must exercise the same path used by the registered live trigger.",
            "Declare the exact manifest.json JSON in metadata_files: UniqueID must equal "
            "loader_identity and EntryDll must match the built assembly filename. Implement "
            "public override object GetApi() on the SMAPI Mod entry class, returning one public API "
            "object. Every declared entrypoint must be a public instance method on that object with "
            "an exact signature, ordered CLR parameter types and a non-void return type/schema. "
            "Use unambiguous public results, with exact field names or invariant string formatting. "
            "Console handlers call this same API instance and use its return values; the verifier "
            "obtains it through non-generic helper.ModRegistry.GetApi(loader_identity) after game launch "
            "and invokes precisely those reflected public methods. Do not invent static Loaded/LastX "
            "instrumentation or make test correctness depend on guessed log messages.",
            "SDate's day-of-month property is Day; there is no DayOfMonth member. "
            "HoeDirt, Tree and other terrain features live in the StardewValley.TerrainFeatures "
            "namespace; import or qualify it in every file that uses them, and Game1 lives in "
            "StardewValley. ICommandHelper has no Log method: register console commands with "
            "Helper.ConsoleCommands.Add and write output through this.Monitor.Log. Farmer exposes "
            "children only through the getChildren() method, not a property.",
            "The SMAPI date helper is StardewModdingAPI.Utilities.SDate; include its actual namespace "
            "when using it. SDate is not a type in StardewValley. In SMAPI 4.1.10 its Season "
            "property is the StardewValley.Season enum, not a string. Use Season.ToString() "
            "when a string is required. SDate.Now() is a static METHOD, not a property. "
            "Context is in namespace StardewModdingAPI; import or qualify it in every file that uses it.",
            "SMAPI 4.1.10 SDate.AddDays throws System.ArithmeticException when the resulting date "
            "precedes Spring 1 Year 1. Catching only OverflowException will NOT handle it: "
            "OverflowException is a subclass, not a superclass, of ArithmeticException. "
            "Handle the documented invalid-date boundary without swallowing unrelated errors.",
            "When the public contract specifies flooring world coordinates to tiles, preserve "
            "floating-point precision through zoom and viewport addition, then floor the final "
            "quotient. Do not cast a fractional screen/zoom intermediate to int. Respect household "
            "scope exactly when a child input is specified as belonging to the current player.",
            "Preserve source-supported input domains and numerical bounds in behavior capsules. "
            "Do not claim arbitrary unbounded integer support or a clamping policy unless the "
            "capsule establishes it; do not invent new boundary requirements merely for testing.",
        ),
        verifier_contract=(
            "For Stardew return only tests/TaskSuite.cs in files. Do not generate tests/test.sh: "
            "the operator renders a trusted shell runner from case_ids with fixed build, deployment, "
            "timeout and fail-closed verdict checks. The details below describe the provided environment.",
            "Game1.viewport has type xTile.Dimensions.Rectangle, not Microsoft.Xna.Framework.Rectangle. "
            "Use var to preserve its actual type or fully qualify the xTile type.",
            "OnEntry executes during mod loading, before GetApi is ready. Store the IModHelper in "
            "OnEntry; retrieve/retry the target API inside the later world-phase cases (or after "
            "GameLaunched), never cache a null GetApi result from OnEntry as the final API value.",
            "Use the NON-GENERIC helper.ModRegistry.GetApi(loader_identity) overload for reflection. "
            "SMAPI 4.1.10 rejects GetApi<object>() because its generic overload requires a public "
            "interface type, not System.Object. The non-generic overload returns the raw API object.",
            "When MethodInfo.Invoke fails, unwrap TargetInvocationException.InnerException and "
            "rethrow it with ExceptionDispatchInfo.Capture(inner).Throw() so the harness reports "
            "the real failure type/message. Never turn invocation exceptions into passing results.",
            "Game1.season is a StardewValley.Season enum (Season.Spring/Summer/Fall/Winter), "
            "not a string. Save it as Season (or var) and assign enum members when setting a "
            "test date; do not assign string values such as \"spring\" to Game1.season.",
            "For independent birthday oracles use a consistent zero-based absolute day: "
            "t=112*(year-1)+28*(int)season+(day-1), birth=t-daysOld. A yearless birthday uses "
            "r=((birth%112)+112)%112, seasonIndex=r/28, day=r%28+1. Do not add the 1-based "
            "offset twice. For example Spring 1, Year 1 minus 100000 days is Spring 17 "
            "without a year. Keep the oracle independent of the mod's implementation.",
            "Do not assume the fixture's date makes an age of 5 or 10 days fall inside year 1. "
            "Set and restore an explicit calendar date in each birthday case: use a later year "
            "for normal-with-year behavior and an early date with an older child for the fallback. "
            "Keep setup and invocation in the same synchronous case and restore state in finally.",
            "All assertions depending on a fixture must execute before its finally restores state. "
            "If a helper sets zoom/viewport, invokes the API, asserts, then restores them, do not "
            "invoke the API again outside that helper and compare to the old fixture's expected tile.",
            "Pinned API facts checked against the real 1.6.15.24356 assemblies: Options.zoomLevel "
            "has no setter. Set and restore Game1.options.baseZoomLevel (a public float field) "
            "for immediate zoom scenarios; preserve other original settings in finally. "
            "FarmHouse.getChildren() returns a newly materialized list, not a live mutation "
            "collection. Add/remove fixture Child objects through that home's characters "
            "collection, then assert the home.getChildren() query actually sees the fixture "
            "before invoking the mod API. Restore the exact fixture objects afterward. "
            "A broken fixture is a test-authoring failure, not evidence of a mod defect.",
            "The child fixture constructor signature is Child(string name, bool isMale, "
            "bool isDarkSkinned, Farmer farmer); use Game1.player and then set daysOld.Value.",
            "Resolve the player's house with Utility.getHomeOfFarmer(Game1.player). "
            "Do not invent Farm.GetHouseOfPlayer or other lookup methods.",
            "For zoom FAIL_TO_PASS cases, the corrected and zoom-ignoring formulas must land "
            "in different tiles, not just different world pixels. Check the arithmetic when choosing "
            "the fixture. With 64px tiles a valid fractional-negative witness is baseZoomLevel=2, "
            "viewport=(-65,0), screen=(1,0): corrected tile=(-2,0), ignoring zoom=(-1,0). "
            "Do not replace this requirement with a sample whose two formulas floor to the same tile.",
            "Use the existing trusted GcbHarness project at /opt/gcb/harness/GcbHarness/"
            "GcbHarness.csproj; do not invent, replace or reimplement its framework or result writer. "
            "Compile tests/TaskSuite.cs into this project at verification time.",
            "TaskSuite must be a public parameterless class implementing GcbHarness.Framework.IGcbSuite: "
            "string GroupName { get; }, IEnumerable<GcbCase> Cases { get; }, and optional "
            "void OnEntry(StardewModdingAPI.IModHelper helper). OnEntry runs before the world loads.",
            "GcbCase.Sync(string name, Action body, GcbPhase phase = GcbPhase.World) creates a sync case; "
            "new GcbCase(string name, Func<System.Collections.IEnumerator> body, int timeoutTicks = 600, "
            "GcbPhase phase = GcbPhase.World) creates a coroutine. Use GcbWait.Ticks(int) or "
            "GcbWait.Until(Func<bool>) for game ticks. GcbPhase.Title runs before the fixture save loads; "
            "GcbPhase.World runs in the real loaded world. Enumerate exactly every case_ids name once.",
            "Available assertions include GcbAssert.IsTrue(bool, string), "
            "GcbAssert.AreEqual<T>(T expected, T actual, string), and GcbAssert.IsNotNull(object?, string). "
            "The harness catches assertion exceptions and continues other cases. Use actual shared "
            "public mod entrypoints and live game state, with an independent expected-behavior oracle; "
            "source text scans or successful compilation cannot establish any behavior case.",
            "tests/test.sh must use set -euo pipefail and declare exactly one unquoted line EXPECTED=N "
            "where N equals len(case_ids). The evaluator copies the submission to /app/mod; build "
            "/app/mod/Synthetic.sln in Release without network using GamePath=/opt/stardew, deploy "
            "the actual DLL and manifest to /opt/stardew/Mods/<neutral-name>, copy /tests/TaskSuite.cs "
            "into the trusted harness, build it, and deploy its DLL and manifest to "
            "/opt/stardew/Mods/GcbHarness. Any harness references to generated public types must be "
            "resolved against the mod assembly or inspected via the non-generic public GetApi contract.",
            "Run /opt/stardew/StardewValley with xvfb-run and a bounded timeout, "
            "GCB_MODE=run-suite, GCB_RESULT_PATH=/logs/verifier/result.json, and GCB_SAVE_NAME read from "
            "/opt/gcb/save-name.txt. Preserve build and game logs under /logs/verifier. Do not generate "
            "or modify result.json in the shell or suite; only the running trusted harness writes it.",
            "The trusted result envelope has lowercase keys group, fatal, passed, failed, cases. "
            "Each case has PascalCase Name, Passed, Error, Ticks. A shell gate must require fatal null, "
            "exact unique expected case names/count, integer totals equal to the case outcomes, "
            "and every Passed true before writing reward.txt=1; otherwise write 0 and fail. "
            "A missing/malformed verdict, build/boot failure or skipped assertion must fail closed. "
            "Never synthesize passing result rows when the real game cannot execute.",
        ),
    ),
    "isaac-rebirth": GameAuthoringSpec(
        game_id="isaac-rebirth",
        plugin_id="isaac-rebirth",
        pack_directory="isaac-synth",
        starter_directory="mod",
        runtime_id="afterbirth-plus-1.06.t1-synth",
        project_requirements=("main.lua", "metadata.xml"),
        verifier_requirements=(
            "tests/test.sh",
            "tests/suite.lua",
            "tests/Dockerfile",
        ),
        generation_contract=(
            "Produce a complete anonymous Afterbirth+ Lua mod. Returned file paths are relative "
            "to its root: main.lua and metadata.xml have no mod/ prefix.",
            "Use only APIs present in Afterbirth+ v1.06.T1.",
            "The verifier must declare and execute exactly 35 unique assertion cases.",
            "The verifier Dockerfile must declare ARG PRIVATE_IMAGE and use FROM ${PRIVATE_IMAGE}.",
        ),
    ),
    "garrys-mod": GameAuthoringSpec(
        game_id="garrys-mod",
        plugin_id="garrys-mod",
        pack_directory="garrys-mod-synth",
        starter_directory="gamemode",
        runtime_id="gmod-gluatest-synth",
        project_requirements=("gamemode/init.lua", "gamemode/cl_init.lua"),
        verifier_requirements=(
            "tests/test.sh",
            "tests/suite.lua",
        ),
        model_authored_verifier=("tests/suite.lua",),
        trusted_shell_runner="tests/test.sh",
        generation_contract=(
            "Produce a complete anonymous GLua gamemode. Returned paths are relative to its "
            "content root and include gamemode/init.lua and gamemode/cl_init.lua exactly.",
            "It must boot on the pinned Garry's Mod dedicated server and expose only public GLua APIs.",
        ),
        verifier_contract=(
            "For Garry's Mod return only tests/suite.lua in files. Do not generate tests/test.sh: the "
            "operator renders a trusted shell runner from case_ids. It installs the submission as the "
            "active gamemode on a headless dedicated server (map gm_construct, no players), copies the "
            "suite to lua/tests/gcb_suite/suite.lua, runs the pinned GLuaTest runner once with a two "
            "minute budget, and audits results before any submission-visible hook can alter them.",
            "tests/suite.lua is one GLuaTest file that returns a table: "
            "return { groupName = \"<neutral name>\", cases = { { name = \"<case id>\", "
            "func = function() ... end }, ... } }. "
            "It runs in the server realm after the gamemode has loaded. Every case_ids entry must appear "
            "exactly once as a case name, character for character, and no other case may exist: a "
            "missing, extra, duplicated, skipped or empty case makes the whole run incomplete.",
            "Assert with GLuaTest expectations inside func: expect( value ).to.equal( expected ), "
            ".to.deepEqual( table ), .to.beTrue(), .to.beFalse(), .to.beNil(), .to.exist(), "
            ".to.beA( \"function\" ), "
            ".to.succeed() / .to.err() for a function value, and the negated .toNot forms. A case with "
            "no expectation is reported as empty and fails. For timer or hook driven behavior use "
            "async = true, timeout = <seconds>, and call done() after the final expectation.",
            "Reach the submission only through its declared public entrypoints, hooks and globals. "
            "There are no connected players: build server-side stand-ins or spawned entities yourself, "
            "and clean up hooks, timers and entities you create so cases stay independent.",
        ),
    ),
    "minecraft": GameAuthoringSpec(
        game_id="minecraft",
        plugin_id="minecraft",
        pack_directory="minecraft-synth",
        starter_directory="plugin",
        runtime_id="paper-1.21.11-132-synth",
        project_requirements=("src/main/resources/plugin.yml",),
        verifier_requirements=("tests/test.sh", "tests/TaskSuite.java"),
        model_authored_verifier=("tests/TaskSuite.java",),
        trusted_shell_runner="tests/test.sh",
        project_path_prefixes=("src/main/java/", "src/main/resources/"),
        source_lint=MINECRAFT_SOURCE_LINT,
        generation_contract=(
            "Produce a complete anonymous Paper server plugin in Java. Returned file paths are "
            "relative to the plugin root: src/main/resources/plugin.yml and src/main/java/<package "
            "path>/*.java only, with no plugin/ prefix, no build.gradle, pom.xml, gradle wrapper, "
            "settings file, src/test tree or any other file. The trusted verifier compiles "
            "src/main/java with javac --release 21 against the server classpath and packages it "
            "with src/main/resources; there is no Gradle, Maven or dependency download.",
            "Target Paper 1.21.11 (build 132) on Java 21. Use only the org.bukkit, io.papermc.paper "
            "and net.kyori.adventure APIs shipped with that server plus the Java standard library. "
            "Do not reference net.minecraft, org.bukkit.craftbukkit, NMS, mixins, third-party "
            "libraries, plugin dependencies, or a plugin.yml libraries/depend/softdepend/load entry.",
            "Choose one neutral lowercase package such as <neutral>.<plugin> and keep every class "
            "below src/main/java in that package tree. The main class extends "
            "org.bukkit.plugin.java.JavaPlugin, registers everything from onEnable, and must not "
            "call System.exit, Bukkit.shutdown, spawn threads that touch game state, or block the "
            "main thread.",
            "Declare the exact plugin.yml in metadata_files: name equals loader_identity (the "
            "plugin's case-sensitive registry name), main is the fully qualified main class, version "
            "is a neutral string and api-version is the quoted string '1.21'. plugin.yml is frozen "
            "shared metadata; do not add commands you do not register in code, and register "
            "every declared command executor in onEnable.",
            "Every behavior must be reachable in the live server through a public observable entry "
            "point: a registered command (executed by the console sender with explicit arguments "
            "and deterministic reply text), a Bukkit event handler reacting to an event the "
            "verifier can construct and call, a scheduler task with a stated tick delay, "
            "configuration values, or a public non-void method on the JavaPlugin main class (or a "
            "public service object it returns) whose signature the interface contract fixes "
            "exactly. Name the exact entry point, argument order and return schema in the "
            "interface contract; never rely on log lines, static fields or Loaded flags.",
            "There are no connected players. Behavior must be observable from the console sender, "
            "from public plugin methods, from entities and blocks in the loaded world, or from "
            "events the verifier fires itself. Do not require a real Player object, a client, "
            "chat, or network access. Do not require a specific world seed or biome.",
            "All logic runs deterministically on the main server thread within one tick unless "
            "the contract names a scheduler delay. Avoid randomness, wall-clock time, system "
            "properties, file I/O outside the plugin data folder, and asynchronous tasks.",
            "Preserve source-supported input domains and numerical bounds in behavior capsules. "
            "Do not claim arbitrary unbounded integer support or a clamping policy unless the "
            "capsule establishes it; do not invent new boundary requirements merely for testing.",
        ),
        verifier_contract=(
            "For Minecraft return only tests/TaskSuite.java in files. Do not generate tests/test.sh, "
            "tests/task.json, a Dockerfile or any build file: the operator renders a trusted runner "
            "from case_ids that compiles the submission with javac, compiles your suite into the "
            "trusted GcbGrader plugin, boots the pinned Paper 1.21.11 dedicated server once "
            "without network or players, and audits the result envelope before any case count is "
            "trusted.",
            "tests/TaskSuite.java declares exactly one public class TaskSuite in package "
            "io.gamecodebench.suite that implements io.gamecodebench.harness.GcbSuite and has a "
            "public no-argument constructor. Every case is one public instance method annotated "
            "@GcbCase(\"<case id>\") whose string equals a case_ids entry character for character; "
            "declare every case_ids entry exactly once and no other case. A synchronous case has "
            "signature (); a ticked case takes a single io.gamecodebench.harness.GcbScript "
            "parameter and builds steps with script.step(...), script.waitTicks(n) and "
            "script.waitUntil(condition, description).",
            "Assert only with io.gamecodebench.harness.GcbAssert: isTrue(boolean, String), "
            "isFalse(boolean, String), equals(Object expected, Object actual, String), "
            "notNull(Object, String), isNull(Object, String), throwsType(Class<T>, GcbRunnable, "
            "String) and fail(String). The harness catches every Throwable per case, records its "
            "message and continues with the next case; do not catch assertion errors yourself, "
            "print result markers, or call System.exit or Bukkit.shutdown.",
            "Reach the submission only through the public interface contract. Obtain the plugin "
            "with org.bukkit.Bukkit.getPluginManager().getPlugin(loader_identity); the suite is "
            "compiled without the submission on its classpath, so call contracted public methods "
            "through java.lang.reflect (unwrap InvocationTargetException and rethrow its cause) "
            "and never import or name the submission's classes or package.",
            "Execute console commands with io.gamecodebench.harness.GcbCommands.dispatch("
            "io.gamecodebench.harness.GcbSenders.recording(), \"<command> <args>\") and read the "
            "recorded sender's messages() (plain text, cleared with clear()). Fire events with "
            "io.gamecodebench.harness.GcbEvents.call(event) and inspect the returned event. Use "
            "io.gamecodebench.harness.GcbWorlds.main() for the loaded world, GcbEntities.spawn/"
            "remove for entities, GcbInventories.create for inventories and GcbProxies.player only "
            "to construct an event argument, never to expect real player behavior.",
            "Include one sentinel case that proves the plugin is enabled, for example "
            "GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(loader_identity), ...). "
            "Keep cases independent: restore world blocks, remove spawned entities, unregister "
            "listeners and clear recorded messages in a finally block.",
            "Use an independent expected-behavior oracle derived from the behavior contract; "
            "source text scans, reflection over private fields or successful compilation cannot "
            "establish any behavior case. Cases run in order on the main thread; a ticked case "
            "that exceeds its tick budget is reported as hung and fails.",
        ),
    ),
}


def game_spec(game_id: str) -> GameAuthoringSpec:
    try:
        return GAME_SPECS[game_id]
    except KeyError as error:
        raise ValueError(f"unsupported authoring game: {game_id}") from error
