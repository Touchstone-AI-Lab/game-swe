# Rhenium integration controls

These controls were run on 2026-09-02 on a Windows 11 Pro for Workstations
(10.0.26200) host against a real Palworld dedicated server. They exercise the
Rhenium attempt pipeline (`rhenium prepare-attempt` then `rhenium run-attempt
--profile full`), not a standalone harness.

## Runtime identity

```text
dedicated server: Palworld Dedicated Server, Steam app 2394010, buildid 24575149
install:          D:\PalServerBench\PalServer (SteamCMD anonymous login)
launched binary:  Pal\Binaries\Win64\PalServer-Win64-Shipping.exe
mod loader:       RE-UE4SS v3.0.1 Beta #0, Git SHA 97b7e501
                  (release asset UE4SS_v3.0.1-1111-g97b7e501.zip,
                   sha256 1bfb8dd545b5dc2b2bcc2a57175b30bc3370ca916cd931a29f7a26133d672692)
mods directory:   Pal\Binaries\Win64\ue4ss\Mods
engine reported:  UE 5.1 (from the UE4SS AOB scan)
```

The catalog pins no build. This record documents the exact build the controls
ran against; it is not a support claim for any other build.

## Base and reference

`nop` is the unmodified starter workspace `prepare-attempt` materialises, which
contains only the exam documents. `gold` is a reference implementation written
against the public contract alone.

| Task | Submission | Run ID | Score | Complete | Passed | Headless cases |
| --- | --- | --- | ---: | --- | --- | --- |
| guild-storage-ledger | gold | `run-5fd060e563cc45a4` | 100 | true | true | 4/4 |
| guild-storage-ledger | nop | `run-f2efbe575d4a401f` | 0 | false | false | 0/0 |
| palbox-transfer-transaction | gold | `run-cba08910adb34c75` | 100 | true | true | 4/4 |
| palbox-transfer-transaction | nop | `run-1f7fecf7d2434b54` | 0 | false | false | 0/0 |
| raid-dispatch-queue | gold | `run-6bb86806268b422f` | 100 | true | true | 4/4 |
| raid-dispatch-queue | nop | `run-235b320ce5604011` | 0 | false | false | 0/0 |
| server-rule-ballot | gold | `run-3dcc3c7fb7284429` | 100 | true | true | 4/4 |
| server-rule-ballot | nop | `run-266157a4399b4f3b` | 0 | false | false | 0/0 |
| damage-attribution-arbiter | gold | `run-db0dbcfa0c3042ce` | 100 | true | true | 4/4 |
| damage-attribution-arbiter | nop | `run-acbbdfe484a841fe` | 0 | false | false | 0/0 |

Every reference run started a real dedicated server, loaded the submission as a
UE4SS Lua mod, and returned a nonce-bound assertion payload. The `nop` bases
have no `scripts/main.lua`, so their headless level cannot run at all and their
result is correctly incomplete as well as failed.

## Discriminating controls

An absent base only proves the level detects absence. These two controls start
from the passing reference and break exactly one dedicated-server behaviour, so
levels 1 and 2 and every integration check still pass.

| Control | Run ID | Score | Complete | Passed | Headless cases |
| --- | --- | ---: | --- | --- | --- |
| guild-storage-ledger, service published as `RheniumSvc` | `run-fac5db5ebb924140` | 70 | true | false | 1/4 |
| damage-attribution-arbiter, server `Observe` drops `duplicate` | `run-dbd8925b1ef54549` | 90 | true | false | 3/4 |

The first fails every assertion that needs the published global; the second
fails only `out-of-order reports resolve deterministically on the server` with
`a repeated sequence was applied on the server`, while its plain-Lua module
still passes the sandboxed suite. The headless level is therefore load-bearing
rather than a presence check.

## Findings this validation closed

The first real run showed that the pack and plugin could not have passed on any
host, because they were authored without a dedicated server to try them on:

- `UGameplayStatics::IsDedicatedServer` is stripped from Palworld's shipping
  build. The class exposes 137 reflected functions and that is not one of them,
  so `helpers.GetGameplayStatics():IsDedicatedServer(world)` raised
  `attempt to call a TrivialObject value`. Every task's first headless
  assertion failed regardless of the submission.
  `UKismetSystemLibrary::IsDedicatedServer` is present and returns `true`.
- `NotifyOnNewObject("PalPlayerController", ...)` is refused: UE4SS requires a
  full class path such as `/Script/Pal.PalPlayerController`.
- UE4SS starts Lua mods roughly one second into startup, about five seconds
  before the dedicated server owns a valid `UWorld`. A top-level authority
  guard therefore returns early and never mounts anything.
- `PalServer.exe` is a launcher that spawns `PalServer-Win64-Shipping-Cmd.exe`.
  Terminating the launcher left a live orphan holding the UE4SS mods directory.
- UE4SS `print` output never reaches the server's stdout; the run captured zero
  bytes there. `UE4SS.log` and the result file are the only assertion channels.

## Cleanup check

After the twelve runs above, no `PalServer*` process remained, `mods.txt` was
byte-identical to its pre-run content, and no `rhenium_<hex>` directory was left
in the UE4SS mods directory.
