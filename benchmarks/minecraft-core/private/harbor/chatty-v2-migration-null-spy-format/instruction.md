# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# Chatty: a migrated v2 configuration breaks the plugin and loses its language

## Context

`plugin/` is the Chatty chat-management plugin (MIT) at an upstream commit. It
is a Gradle multi-module build: `api/` holds the public `ru.brikster.chatty.api`
types and `spigot/` the plugin itself (`spigot/src/main/resources/plugin.yml`,
`name: Chatty`). The shaded plugin jar is `build/libs/Chatty-3.0.0-SNAPSHOT.jar`,
produced by `./gradlew shadowJar`; the upstream JUnit tests run with
`./gradlew test`.

Chatty 3 keeps its configuration in several YAML files under `plugins/Chatty/`
(`chats.yml`, `settings.yml`, `pm.yml`, ...). Chatty 2 used a single
`config.yml`. When the plugin enables and finds a `config.yml` in its data
folder, it moves the folder aside to `Chatty_old_<timestamp>`, generates the v3
files with their defaults, migrates the legacy values into them and loads the
result (`MIGRATION.md` in the repository describes the mapping). `/chatty reload`
re-reads the v3 files and answers with its success message.

Every chat in `chats.yml` has a `spy:` block with `enable` and `format`; the spy
format is the message that players with the spy permission receive for that chat.
In Chatty 2 the spy format was one global template, `spy.format.chat`, whose
`{format}` placeholder stood for the chat's own format; the template Chatty 2
shipped by default was `&6[Spy] &r{format}`, and the whole `spy` section was
optional. Registered chats are visible through `ChattyApi.instance().getChats()`
(each a `ru.brikster.chatty.api.chat.Chat` with `isEnableSpy()` and
`getSpyFormat()`).

The plugin's own messages come in five languages, selected by `language` in
`settings.yml`: `en-US`, `ru-RU`, `de-DE`, `es-ES` and `zh-CN` (shipped as
`lang/<language>.yml`). Chatty 2 selected its language with `general.locale` and
spelled the same languages `en`, `ru`, `de`, `es` and `zh_CN`. The reload success
message is `Plugin successfully reloaded!` in English,
`Плагин успешно перезагружен!` in Russian, `Plugin erfolgreich neu geladen!` in
German, `¡Plugin recargado correctamente!` in Spanish and `插件重载成功！` in
Chinese.

## Symptom

Server owners upgrading from Chatty 2 report two problems.

First, a Chatty 2 `config.yml` that declares its chats but has no top-level
`spy` section breaks the upgraded plugin:

```text
[Chatty] Found legacy "config.yml" file in plugin directory. "Chatty" folder was renamed to "Chatty_old_1790058413411".
[Chatty] Migrating legacy Chatty v2 configuration...
[Chatty] Legacy configuration migrated. Please review the following:
...
[Chatty] Failed to migrate legacy configuration — using defaults
ru.brikster.chatty.shaded.com.google.inject.ProvisionException: Unable to provision, see the following errors:
...
Caused by: java.lang.NullPointerException: input
```

The plugin stays enabled and `/chatty` still answers, but the migrated chats
never load (the chat registry only holds the chats of the default `chats.yml`),
and the migrated `plugins/Chatty/chats.yml` contains, for every chat,

```yaml
    spy:
      enable: true
      format: null
```

Every `/chatty reload` on that configuration fails the same way
(`Error while reloading plugin: ProvisionException. See console for more
details.`). The same `NullPointerException: input` also hits a hand-written v3
`chats.yml` in which a chat's `spy:` block declares only `enable:` and no
`format:`. A `chats.yml` whose every chat has an explicit `spy.format` reloads
fine, and a v2 file that does carry a `spy.format.chat` template migrates
correctly.

Second, servers that ran Chatty 2 in another language come up in English after
the upgrade: `general.locale` is not carried over, and writing the language the
way Chatty 2 spelled it (`language: ru` or `language: zh_CN`) into `settings.yml`
silently gives English as well, with nothing in the console.

## Task

Repair the plugin so that:

- Migrating a v2 `config.yml` that has no `spy` section (or no
  `spy.format.chat`) gives every migrated chat a spy format in the written
  `chats.yml`, built from Chatty 2's default template `&6[Spy] &r{format}` with
  `{format}` replaced by that chat's own v2 `format`. For a v2 chat with
  `format: '&e[GCB Local] &r{player}: {message}'` the written value is
  therefore `&6[Spy] &r&e[GCB Local] &r{player}: {message}`. A v2 chat that
  declared no `format` must still receive a non-blank spy format built from the
  same template (the `{format}` placeholder replaced, not left in place).
- After that migration the chats declared in the v2 file are registered with
  their migrated properties (range, symbol, display name, permission flag, chats
  disabled in v2 left out), spy is enabled on them (the v2 default),
  `Chat#getSpyFormat()` renders the template around the chat's format, and
  `/chatty reload` on the migrated files succeeds with the chats still
  registered.
- A `chats.yml` whose chat has a `spy:` block with only `enable: true` loads on
  `/chatty reload`: the chat is registered with `isEnableSpy()` true and a
  non-null `getSpyFormat()`.
- The v2 `general.locale` is migrated: a v2 locale that names one of the five
  languages, in either spelling, becomes that language in `settings.yml`
  (`ru` is written as `language: ru-RU`), and the migrated plugin answers in it.
- `language` in `settings.yml` accepts the Chatty 2 spellings and a bare
  language code as the matching supported language, ignoring case and treating
  `_` like `-` (`zh_CN` selects `zh-CN`, `ru` selects `ru-RU`). A value that
  matches no supported language falls back to English and is reported in a
  console record at level `WARNING` or higher that names the configured value.
- Explicit values keep winning: a `spy.format` written in `chats.yml` is used
  verbatim (and stays in the file after a reload), a v2 `spy.format.chat`
  template is still applied as before, chats that disable spy stay disabled, and
  a supported language tag in `settings.yml` (for example `de-DE`) is applied as
  before.
- `/chatty`, `/chatty reload`, the rest of the migration and the rest of the
  plugin behave exactly as before.

Keep the change inside `plugin/spigot/src/main/java` (you may also touch
`plugin/api/src/main/java` if you need to). The build files (`build.gradle`,
`settings.gradle`, `api/build.gradle`, `spigot/build.gradle`), the Gradle
wrapper and the existing tests under `plugin/spigot/src/test` are frozen: the
verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream JUnit suite (`test`), and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. The server starts
with a Chatty 2 `plugins/Chatty/config.yml` with `general.locale: ru` that
declares several chats (one with no `format`, one with `enable: false`) and has
no `spy` section. The grader dispatches `/chatty` and `/chatty reload` from a
console sender and checks the replies, inspects `ChattyApi.instance().getChats()`
(registration, range, symbol, display name, permission flag, `isEnableSpy()`,
`getSpyFormat()` rendered as plain text) and reads the migrated
`plugins/Chatty/chats.yml` and `settings.yml`. It then writes a `chats.yml` with
explicit spy formats, sets `language` in `settings.yml` to a supported tag, to a
Chatty 2 spelling and to an unsupported value, and finally writes a `chats.yml`
whose chat has a `spy:` block with only `enable: true`, reloading after each and
checking the replies, the console warnings, the registry and the files again.
