# Chatty: one bad notification channel stops the whole plugin from enabling

## Context

`plugin/` is the Chatty chat-management plugin (MIT) at an upstream commit. It
is a Gradle multi-module build: `api/` holds the public `ru.brikster.chatty.api`
types and `spigot/` the plugin itself (`spigot/src/main/resources/plugin.yml`,
`name: Chatty`). The shaded plugin jar is `build/libs/Chatty-3.0.0-SNAPSHOT.jar`,
produced by `./gradlew shadowJar`; the upstream JUnit tests run with
`./gradlew test`.

Chatty keeps its configuration in several YAML files under `plugins/Chatty/`.
`notifications.yml` declares periodic notifications in four sections (`chat`,
`actionbar`, `title`, `advancements`), each with a `lists:` map of channel id to
channel settings; a section left out of the file gets its shipped default
channels. Every channel has a `period` in seconds. An action bar channel also has
`stay`, the number of seconds its message stays on screen, which must not exceed
its `period` (equal is allowed). `/chatty reload` (console permission
`chatty.command.reload`) re-reads every file and answers
`Plugin successfully reloaded!`.

## Symptom

Put an action bar channel whose `stay` is larger than its `period` into
`plugins/Chatty/notifications.yml`:

```yaml
actionbar:
  enable: true
  lists:
    default:
      period: 60
      stay: 60
    broken:
      period: 5
      stay: 10
    other:
      period: 7
      stay: 3
```

Start the server and Chatty fails to enable: the console shows a long stack trace
that names neither the file nor the channel, and the server has no chat
formatting and no Chatty commands. If the file is edited while the server is
running instead, `/chatty reload` answers
`Error while reloading plugin: ProvisionException. See console for more details.`,
and from then on the plugin no longer formats chat, no longer reacts to players
joining and its notifications stop, until the server is restarted with a valid
file. Channels listed after the bad one (`other` above) never come into effect.
An owner who makes one typo in this file loses the whole plugin and is not told
where the typo is.

## Task

Repair the plugin so that a notification channel that cannot be used never takes
the plugin down:

- With such a file, `/chatty reload` (and start-up) completes normally and
  answers `Plugin successfully reloaded!`.
- Every offending channel is skipped and reported. Skipped channels are not
  registered. For each one the plugin logs a record at level `WARNING` or higher,
  through the plugin's logger or another `java.util.logging` logger that reaches
  the server console, whose message contains the channel id (for example
  `broken`) and says why the channel was skipped. When a file has several
  offending channels, each of them is reported.
- Every other channel of the file is registered exactly as before, including
  channels listed after an offending one and the channels of the other sections.
- After such a reload the plugin keeps working: it still handles chat (its
  listener for Paper's `AsyncChatEvent` or for `AsyncPlayerChatEvent` stays
  registered), still listens to `PlayerJoinEvent`, the chat registry
  (`ChattyApi.instance().getChats()`) still holds the shipped `local` and
  `global` chats, and the registered notifications keep advancing.
- Valid configurations behave exactly as before: a channel whose `stay` equals
  its `period` is registered, a missing `notifications.yml` is regenerated with
  the shipped channels (`donate` and a `default` channel in each of the chat,
  action bar and title sections), notifications advance after a reload, and
  `/chatty` (the plugin summary, which mentions `reload`) keeps answering a
  console sender.

Keep the change inside `plugin/spigot/src/main/java` (you may also touch
`plugin/api/src/main/java` if you need to). The build files (`build.gradle`,
`settings.gradle`, `api/build.gradle`, `spigot/build.gradle`), the Gradle
wrapper and the existing tests under `plugin/spigot/src/test` are frozen: the
verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream JUnit suite (`test`), and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. There it writes
several versions of `plugins/Chatty/notifications.yml` (the generated default, a
valid file, files with one and with two action bar channels whose `stay` exceeds
their `period`) and runs `/chatty reload` from a console sender after each,
checking the reply, the console warnings, the registered event listeners, the
chat registry and the plugin's notification channels.

Paper closes a plugin's class loader when it is disabled, so the grader never
disables and re-enables Chatty; `/chatty reload` and start-up build the
configuration through the same code. The grader reads the registered channels
from the plugin itself, so keep these as they are: the `Chatty` field that holds
the plugin's (relocated) Guice `Injector`, the
`ru.brikster.chatty.notification.NotificationTicker` binding in that injector,
the ticker's collection of registered `Notification` objects, each
notification's `name` field and the `tick` counter that every notification
inherits from `ru.brikster.chatty.notification.Notification`.
