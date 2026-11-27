# Maintenance notes: chatty-v2-migration-null-spy-format

## Upstream

- Repository: https://github.com/Brikster/Chatty, branch `v3` (MIT, `LICENSE`
  kept in the starter: "MIT License / Copyright (c) 2018 Ilya Andreev").
- Base commit: `b9a064587cd22b2151a6386979fad85e141f2b3f` (parent of the
  earliest fix, "Keep the native Adventure prefix out of relocation").
- Fixes (0.2.0 merges two adjacent upstream commits of the same family, both
  "a migrated v2 configuration does not reflect what v2 configured", both by the
  maintainer on 2026-08-08, both touching `V2ConfigMigrator`):
  1. `f20b64b3904f595764fa6147066e07d715e2bedc` "Never migrate a v2 chat to a
     null spy format" (parent `b9a0645`);
  2. `b620b36c62fabfaebfbe22a7e305108e77355629` "Migrate the v2 locale to a v3
     language" (parent `f20b64b`).
  The catalog's `fix_commit` is the later one; the reference is the combined
  change `b9a0645..b620b36`, trimmed to `spigot/src/main`. Neither commit has a
  separate issue. Both ship test changes
  (`V2ConfigMigratorTest`, a new `UserEditedConfigTest`) that are not part of the
  frozen base test set.
- The starter is `git archive` of the base commit without `.github/` and
  `scripts/` (smoke-test JavaScript and a v2 fixture that do not take part in
  the build). `docs/` does not exist upstream. The starter is unchanged from
  0.1.0.
- The next upstream commit, `4072f98` "Stop a failed v2 migration from leaving
  a dead plugin behind", changes what `Chatty.onEnable` does when the
  post-migration `initialize()` throws. It is a different code path, it is the
  fix of `chatty-failed-migration-dead-plugin` (whose starter is `b620b36`), and
  it is not part of this task; the suite relies on the base behaviour (plugin
  stays enabled, `/chatty` registered) only through the sentinel and preserved
  cases.

## Defect

`V2ConfigMigrator.migrateChats` writes a `spy:` block for every migrated chat
but only puts a `format` into it when the legacy file had a
`spy.format.chat` template *and* the chat had a `format`. A v2 `config.yml`
without a top-level `spy` section (the section was optional in v2) therefore
migrates every chat to `spy: {enable: true}`; okaeri then serialises the
missing `ChatSpyConfig.format` as `format: null`, because the field has no
initialiser. `ConfigsLoader.loadChannels` passes
`chatConfig.getSpy().getFormat()` straight to
`InternalMiniMessageStringConverter.stringToComponent`, whose
`MiniMessage.deserialize` rejects null (`NullPointerException: input`).

At the base `Chatty.onEnable` catches the failure of the post-migration
`initialize()` ("Failed to migrate legacy configuration — using defaults") and
still registers `/chatty`, so the plugin is enabled but dead: the listeners
were unregistered by `closeResources()`, the chat registry exposed through
`ChattyApi` is the one built from the default `chats.yml` before the
migration, and every `/chatty reload` on the migrated files fails with the
same `ProvisionException` (`Error while reloading plugin: ProvisionException`).
A hand-written v3 `chats.yml` whose spy block declares only `enable` fails the
same way.

The second commit's defect: `V2ConfigMigrator` never read `general.locale`, so
every migrated server came up in English. Copying the value would not have
helped: v2 spelled locales `ru`, `zh_CN`, ... while
`GeneralGuiceModule` accepted only the exact tags `en-US`, `ru-RU`, `de-DE`,
`es-ES`, `zh-CN` and silently replaced anything else with `en-US`, with no log
line. A hand-written `language: ru` or `language: zh_CN` in `settings.yml`
therefore also gives English.

## Reference fix

`solution/after/` carries the combined upstream main-source change (five files):

- `config/migration/V2ConfigMigrator.java`: when the legacy file has no
  `spy.format.chat`, use v2's default template `&6[Spy] &r{format}`; when the
  chat has no v2 `format`, substitute `{prefix}{player}{suffix}&8: &f{message}`
  so `{format}` is always replaced and `spy.format` is always written (first
  commit); `general.locale` is mapped through
  `SettingsConfig.matchSupportedLanguage` into `settings.yml`'s `language`, and
  an unmappable locale is listed in the migration notes (second commit).
- `config/file/ChatsConfig.java`: `ChatSpyConfig.format` defaults to `""`, so a
  spy block without `format` loads as an empty string.
- `guice/ConfigsLoader.java`: a null spy format is converted as `""` instead
  of being handed to MiniMessage.
- `config/file/SettingsConfig.java`: `SUPPORTED_LANGUAGES` and
  `matchSupportedLanguage` (exact tag ignoring case, `_` treated as `-`, then a
  bare language code).
- `guice/GeneralGuiceModule.java`: the loader matches the configured language
  through `matchSupportedLanguage` and logs a WARNING naming an unsupported value
  before falling back to `en-US`.

The base tests (48) pass with and without the fix (offline).

## Build

Gradle 8.8 wrapper, modules `api` and `spigot`, JDK 21 toolchain
(`org.gradle.java.installations.auto-download=false` is satisfied by the
image's JDK), `sourceCompatibility` 11, `compileOnly spigot-api 1.19-R0.1`.
The plugin jar is `spigot:shadowJar`, written to the root
`build/libs/Chatty-3.0.0-SNAPSHOT.jar`; `shadowJar` also resolves the dedicated
`sqliteDriver` configuration (embedded as `sqlite-jdbc.jardata`), so the
warm-up must run `shadowJar`, not `assemble`. Tests are JUnit 5 + Mockito (no
MockBukkit); reports land in `spigot/build/test-results/test/`. The whole
`net.kyori` package is relocated to `ru.brikster.chatty.shaded.net.kyori` at
this base, so `Chat#getSpyFormat()` returns the shaded `Component` type and the
suite renders it with the shaded `PlainTextComponentSerializer`.

Frozen paths are declared explicitly in the catalog (`build.frozen_paths`)
because the defaults are root-only: `api/build.gradle`, `spigot/build.gradle`,
`api/src/test`, `spigot/src/test` are added; `api/src/test` and
`gradle.properties` do not exist upstream and restore as "nothing".

Harness requirements (all present in the repository harness that the scratch
pack copies): recursive JUnit report discovery, `tests/seed/<PluginName>/...`
copied into the server's `plugins/` before start-up (`seed_plugin_data`) and
`COPY seed /tests/seed` emitted by `materialize.py`; `rhenium_minecraft.catalog`
accepts `plugin.yml` under `spigot/src/main/resources/`.

## Why the repository matters

The solver has to follow the value from the v2 file through the migrator into
the generated `chats.yml`, through okaeri's serialisation of a null field, into
`ConfigsLoader` and the MiniMessage converter, and understand that both the
migration output (an admin-visible file) and the loader (a hand-written v3 file
with a minimal spy block) need handling. A guard in the loader alone leaves
`spy.format: null`/blank in the migrated file, so spies would receive an empty
message and the file the admin is told to review is wrong; a migrator-only fix
still crashes on a spy block that declares only `enable`. The default template
is a v2 fact the solver must recover (the exam states it).

Since 0.2.0 the exam no longer quotes the stack frames (`ConfigsLoader`,
`InternalMiniMessageStringConverter`) and no longer names the migrator; and the
second defect sits in two more places: the migrator (which never reads
`general.locale`) and the language selection in `GeneralGuiceModule` (which
rejects the v2 spellings without a word). A repair that maps the locale in the
migrator only still gives English for a hand-written `language: zh_CN` and
reports nothing for an unknown value; one that normalises in the loader only
leaves the migrated `settings.yml` on `en-US`.

## Live-server design

No player is needed. The server starts with `tests/seed/Chatty/config.yml`, a
Chatty 2 file with chats `local` (format, range 100, cooldown), `global`
(format, symbol `!`, range -1), `gcbstaff` (display name, permission, no
format) and `gcbretired` (`enable: false`), and no `spy` section. Chatty
renames the folder and migrates on the real enable. Observation points:
`ChattyApi.instance().getChats()` (the `Chat` API, spy format rendered through
the shaded `PlainTextComponentSerializer`), the migrated
`plugins/Chatty/chats.yml` read with Bukkit's `YamlConfiguration`, and
`/chatty` / `/chatty reload` dispatched from a `GcbSenders.recording()` console
sender (Chatty's native Adventure provider answers the proxy directly).

Cases, in order:

0. `plugin is enabled` (sentinel): enabled, `/chatty` owned by Chatty,
   `ChattyApi` available. Holds on the starter because `onEnable` catches the
   migration failure and still registers `/chatty`.
1. `chatty command answers the console` (preserved): the info message is
   delivered through the injector that the failed `initialize()` left behind,
   so it holds on the starter.
2. `chats from the legacy config are registered at start-up` (target): the
   registry lists `local`, `global`, `gcbstaff` with migrated properties, not
   `gcbretired`; on the starter the registry is the default one (no `gcbstaff`).
3. `migrated chats carry a spy format` (target): `chats.yml` carries
   `&6[Spy] &r<v2 format>` for `local`/`global` and a non-blank, placeholder-free
   spy format for `gcbstaff`; the API renders `[Spy]` around `[GCB Local]`. On
   the starter the file has `format: null`.
4. `chatty reload succeeds on the migrated configuration` (target): the reload
   answers `Plugin successfully reloaded!`; on the starter it answers
   `Error while reloading plugin: ProvisionException`.
5. `explicit spy formats survive a reload` (preserved): a fully explicit
   `chats.yml` reloads, the explicit `[Watch ...]` formats reach the API and stay
   in the file, spy stays disabled where disabled. Holds on the starter (the
   explicit file has no null to convert; verified after the failed reload of
   case 4 in the exploration run).
6. `spy section with only enable reloads` (target): a `chats.yml` whose
   `gcbminimal` chat has `spy: {enable: true}` only reloads and registers the
   chat with a non-null spy format; on the starter the reload fails with the
   NullPointerException.

Exploration evidence for the exam's console excerpt: the base jar on the real
server with the same seed (scratch `explore/explore-base.log`).

0.2.0 cases (the seed now has `general.locale: ru`, so with a repaired plugin
every reply is in Russian until the suite changes the language; the reload check
of the existing cases accepts the success message of any bundled language):

5. `the v2 locale is migrated to the v3 language` (target): the migrated
   `settings.yml` has `language: ru-RU` and `/chatty reload` answers
   `Плагин успешно перезагружен!`. Starter: `en-US` (and the reload fails).
6. `explicit spy formats survive a reload` (preserved, was 5).
7. `a supported language tag in settings.yml is applied` (preserved):
   `language: 'de-DE'` gives `Plugin erfolgreich neu geladen!`. Holds on the
   starter because case 6 left a loadable `chats.yml`.
8. `a v2 spelling of a language is accepted` (target): `language: 'zh_CN'`
   gives `插件重载成功！`. Starter: English.
9. `an unsupported language is reported and falls back to English` (target):
   `language: 'kl-GL'` gives `Plugin successfully reloaded!` and a
   WARNING-or-higher record containing `kl-GL`. Starter: no record.
10. `spy section with only enable reloads` (target, was 6).

The suite rewrites only the top-level `language:` line of `settings.yml`.
